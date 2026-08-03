import math
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.catalog import Product
from app.models.discovery import SearchQuery
from app.repositories.catalog import BrandRepository, CategoryRepository, ProductRepository
from app.schemas.catalog import (
    BrandOut,
    CategoryFacetBucket,
    CategoryOut,
    FacetBucket,
    ProductCardOut,
    ProductDetailOut,
    ProductFacets,
    ProductImageOut,
    ProductListMeta,
    ProductListOut,
    ProductVariantOut,
)


def to_product_card(product: Product) -> ProductCardOut:
    return ProductCardOut(
        slug=product.slug,
        title=product.title,
        brand=product.brand.name,
        thumbnail_url=product.thumbnail_url,
        price=product.price,
        mrp=product.mrp,
        discount_percent=product.discount_percent,
        rating_avg=product.rating_avg,
        rating_count=product.rating_count,
        currency=product.currency,
        in_stock=product.stock_total > 0,
    )


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.products = ProductRepository(session)
        self.categories = CategoryRepository(session)
        self.brands = BrandRepository(session)

    async def list_products(
        self,
        *,
        category_slug: str | None = None,
        brand_slugs: list[str] | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        gender: str | None = None,
        q: str | None = None,
        sort: str = "-popularity",
        page: int = 1,
        per_page: int = 24,
        user_id: int | None = None,
    ) -> ProductListOut:
        products, total, used_fallback = await self.products.list_products(
            category_slug=category_slug,
            brand_slugs=brand_slugs,
            price_min=price_min,
            price_max=price_max,
            gender=gender,
            q=q,
            sort=sort,
            page=page,
            per_page=per_page,
        )
        brand_facets = await self.products.brand_facets(category_slug=category_slug)
        category_facets = await self.products.category_facets(category_slug)

        if q and page == 1:
            # Logged once per search (page 1 only, not every pagination click) for zero-result
            # analysis and to seed autocomplete's "popular past queries" (spec §14.3/§14.4).
            self.session.add(
                SearchQuery(query=q.strip()[:255], result_count=total, user_id=user_id, created_at=utcnow())
            )
            await self.session.commit()

        return ProductListOut(
            data=[to_product_card(p) for p in products],
            meta=ProductListMeta(
                page=page,
                per_page=per_page,
                total=total,
                total_pages=max(1, math.ceil(total / per_page)),
                has_next=(page * per_page) < total,
                search_fallback=used_fallback,
            ),
            facets=ProductFacets(
                brands=[FacetBucket(value=name, count=count) for name, count in brand_facets],
                categories=[
                    CategoryFacetBucket(slug=slug, name=name, count=count, is_active=is_active)
                    for slug, name, count, is_active in category_facets
                ],
            ),
        )

    async def get_by_slug(self, slug: str) -> ProductDetailOut:
        product = await self.products.get_by_slug(slug)
        if product is None:
            raise NotFoundError(f"Product '{slug}' was not found.")
        return ProductDetailOut(
            slug=product.slug,
            title=product.title,
            subtitle=product.subtitle,
            description=product.description,
            brand=BrandOut.model_validate(product.brand),
            category=CategoryOut.model_validate(product.category),
            gender=product.gender,
            material=product.material,
            base_color=product.base_color,
            currency=product.currency,
            price=product.price,
            mrp=product.mrp,
            discount_percent=product.discount_percent,
            rating_avg=product.rating_avg,
            rating_count=product.rating_count,
            review_count=product.review_count,
            images=[ProductImageOut.model_validate(i) for i in product.images],
            variants=[ProductVariantOut.model_validate(v) for v in product.variants],
        )

    async def similar(self, slug: str, limit: int = 8) -> list[ProductCardOut]:
        product = await self.products.get_by_slug(slug)
        if product is None:
            raise NotFoundError(f"Product '{slug}' was not found.")
        return [to_product_card(p) for p in await self.products.similar(product, limit=limit)]

    async def frequently_bought_together(self, slug: str, limit: int = 4) -> list[ProductCardOut]:
        product = await self.products.get_by_slug(slug)
        if product is None:
            raise NotFoundError(f"Product '{slug}' was not found.")
        products = await self.products.frequently_bought_with(product.id, limit=limit)
        return [to_product_card(p) for p in products]
