from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_optional_user
from app.models.auth import User
from app.schemas.catalog import ProductCardOut
from app.schemas.discovery import NewsletterSubscribeIn, StockAlertIn, WishlistAddIn, WishlistOut
from app.services.discovery_service import NewsletterService, RecentlyViewedService, StockAlertService, WishlistService

router = APIRouter(tags=["discovery"])


@router.get("/wishlist", response_model=WishlistOut)
async def get_wishlist(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await WishlistService(db).get(user.id)


@router.get("/wishlist/slugs", response_model=list[str])
async def get_wishlist_slugs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Cheap membership check for product grids — avoids fetching the full wishlist payload
    just to render a filled/outline heart on every ProductCard."""
    return await WishlistService(db).slugs(user.id)


@router.post("/wishlist/items", response_model=WishlistOut, status_code=201)
async def add_wishlist_item(
    payload: WishlistAddIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await WishlistService(db).add(user.id, payload.product_slug)


@router.delete("/wishlist/items/{product_slug}", response_model=WishlistOut)
async def remove_wishlist_item(
    product_slug: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await WishlistService(db).remove(user.id, product_slug)


@router.get("/recently-viewed", response_model=list[ProductCardOut])
async def get_recently_viewed(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await RecentlyViewedService(db).list(user.id)


@router.post("/products/{slug}/stock-alerts", status_code=204)
async def subscribe_stock_alert(
    slug: str,
    payload: StockAlertIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    await StockAlertService(db).subscribe(variant_id=payload.variant_id, email=payload.email, user=user)


@router.post("/newsletter/subscribe", status_code=204)
async def subscribe_newsletter(payload: NewsletterSubscribeIn, db: AsyncSession = Depends(get_db)):
    await NewsletterService(db).subscribe(payload.email)
