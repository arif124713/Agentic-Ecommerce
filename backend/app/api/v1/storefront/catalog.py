from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_optional_user
from app.core.errors import NotFoundError
from app.models.auth import User
from app.repositories.catalog import BrandRepository, CategoryRepository
from app.schemas.catalog import BrandOut, CategoryOut, ProductCardOut, ProductDetailOut, ProductListOut
from app.services.catalog.product_service import ProductService
from app.services.discovery_service import RecentlyViewedService

router = APIRouter(tags=["catalog"])


@router.get("/products", response_model=ProductListOut)
async def list_products(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None, description="Comma-separated brand slugs"),
    price_min: Decimal | None = Query(default=None),
    price_max: Decimal | None = Query(default=None),
    gender: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str = Query(default="-popularity"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=24, ge=1, le=100),
):
    service = ProductService(db)
    brand_slugs = [b.strip() for b in brand.split(",")] if brand else None
    return await service.list_products(
        category_slug=category,
        brand_slugs=brand_slugs,
        price_min=price_min,
        price_max=price_max,
        gender=gender,
        q=q,
        sort=sort,
        page=page,
        per_page=per_page,
        user_id=user.id if user else None,
    )


@router.get("/products/{slug}", response_model=ProductDetailOut)
async def get_product(slug: str, db: AsyncSession = Depends(get_db)):
    service = ProductService(db)
    return await service.get_by_slug(slug)


@router.get("/products/{slug}/similar", response_model=list[ProductCardOut])
async def get_similar_products(slug: str, db: AsyncSession = Depends(get_db)):
    return await ProductService(db).similar(slug)


@router.get("/products/{slug}/frequently-bought-together", response_model=list[ProductCardOut])
async def get_frequently_bought_together(slug: str, db: AsyncSession = Depends(get_db)):
    return await ProductService(db).frequently_bought_together(slug)


@router.post("/products/{slug}/view", status_code=204)
async def record_product_view(
    slug: str, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_optional_user)
):
    """Fire-and-forget view ping for the recently-viewed rail (spec §14.5) — a no-op for guests,
    since recently_viewed is a per-user table (documented scope: no localStorage fallback)."""
    if user is not None:
        await RecentlyViewedService(db).record(user.id, slug)


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    repo = CategoryRepository(db)
    return await repo.list_active()


@router.get("/categories/{slug}", response_model=CategoryOut)
async def get_category(slug: str, db: AsyncSession = Depends(get_db)):
    repo = CategoryRepository(db)
    category = await repo.get_by_slug(slug)
    if category is None:
        raise NotFoundError(f"Category '{slug}' was not found.")
    return category


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(db: AsyncSession = Depends(get_db)):
    repo = BrandRepository(db)
    return await repo.list_active()
