import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.errors import ConflictError, NotFoundError
from app.core.slug import slugify, unique_suffix
from app.core.timeutil import utcnow
from app.models.catalog import InventoryMovement, Product, ProductVariant
from app.repositories.admin_catalog import AdminBrandRepository, AdminCategoryRepository, AdminProductRepository
from app.schemas.admin_catalog import (
    AdminProductDetail,
    AdminProductListItem,
    AdminProductListMeta,
    AdminProductListOut,
    BrandOption,
    CategoryOption,
    InventoryAdjustIn,
    LowStockVariantOut,
    ProductWriteIn,
    VariantOut,
    VariantWriteIn,
)
from app.services.discovery_service import StockAlertService

logger = structlog.get_logger("blackcart.inventory")


class AdminCatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.products = AdminProductRepository(session)
        self.categories = AdminCategoryRepository(session)
        self.brands = AdminBrandRepository(session)

    # -- products ------------------------------------------------------------------------------

    async def list_products(
        self, *, q: str | None, status: str | None, category_id: int | None, page: int, per_page: int
    ) -> AdminProductListOut:
        products, total = await self.products.list_products(
            q=q, status=status, category_id=category_id, page=page, per_page=per_page
        )
        items = [
            AdminProductListItem(
                id=p.id,
                slug=p.slug,
                title=p.title,
                brand=p.brand.name,
                category=p.category.name,
                price=p.price,
                mrp=p.mrp,
                status=p.status,
                stock_total=p.stock_total,
                thumbnail_url=p.thumbnail_url,
                is_deleted=p.deleted_at is not None,
            )
            for p in products
        ]
        total_pages = max(1, -(-total // per_page))  # ceil division without importing math
        return AdminProductListOut(
            data=items,
            meta=AdminProductListMeta(
                page=page,
                per_page=per_page,
                total=total,
                total_pages=total_pages,
                has_next=(page * per_page) < total,
            ),
        )

    async def get_product(self, product_id: int) -> AdminProductDetail:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product was not found.")
        return self._to_detail(product)

    async def create_product(self, payload: ProductWriteIn) -> AdminProductDetail:
        base_slug = slugify(payload.title)
        slug = base_slug
        if await self.products.slug_exists(slug):
            slug = f"{base_slug}-{unique_suffix()}"

        now = utcnow()
        product = Product(
            public_id=str(ULID()),
            slug=slug,
            title=payload.title,
            subtitle=payload.subtitle,
            description=payload.description,
            brand_id=payload.brand_id,
            category_id=payload.category_id,
            gender=payload.gender,
            material=payload.material,
            base_color=payload.base_color,
            currency=payload.currency,
            mrp=payload.mrp,
            price=payload.price,
            status=payload.status,
            is_featured=payload.is_featured,
            is_trending=payload.is_trending,
            is_new_arrival=payload.is_new_arrival,
            thumbnail_url=payload.thumbnail_url,
            seo_title=payload.seo_title,
            seo_description=payload.seo_description,
            search_keywords=f"{payload.title} {payload.subtitle or ''}".strip(),
            published_at=now if payload.status == "active" else None,
            variants=[],
            images=[],
            attributes=[],
        )
        self.products.add(product)
        await self.session.commit()
        return await self.get_product(product.id)

    async def update_product(self, product_id: int, payload: ProductWriteIn) -> AdminProductDetail:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product was not found.")

        was_active = product.status == "active"
        for field, value in payload.model_dump().items():
            setattr(product, field, value)
        if payload.status == "active" and not was_active:
            product.published_at = utcnow()
        product.search_keywords = f"{payload.title} {payload.subtitle or ''}".strip()
        product.version += 1
        await self.session.commit()
        return await self.get_product(product_id)

    async def soft_delete_product(self, product_id: int) -> None:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product was not found.")
        product.deleted_at = utcnow()
        await self.session.commit()

    async def restore_product(self, product_id: int) -> AdminProductDetail:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product was not found.")
        product.deleted_at = None
        await self.session.commit()
        return await self.get_product(product_id)

    # -- variants ------------------------------------------------------------------------------

    async def add_variant(self, product_id: int, payload: VariantWriteIn) -> VariantOut:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product was not found.")

        variant = ProductVariant(
            product_id=product_id,
            sku=payload.sku,
            size=payload.size,
            color=payload.color,
            color_hex=payload.color_hex,
            mrp=payload.mrp,
            price=payload.price,
            stock=payload.stock,
            low_stock_threshold=payload.low_stock_threshold,
            is_active=payload.is_active,
        )
        self.products.add_variant(variant)
        await self.session.flush()
        if payload.stock > 0:
            self.products.add_movement(
                InventoryMovement(
                    variant_id=variant.id,
                    delta=payload.stock,
                    reason="admin_adjust",
                    balance_after=payload.stock,
                    note="Initial stock on variant creation",
                    created_at=utcnow(),
                )
            )
        await self._recompute_stock_total(product_id)
        await self.session.commit()
        return VariantOut.model_validate(variant)

    async def update_variant(self, variant_id: int, payload: VariantWriteIn) -> VariantOut:
        variant = await self.products.get_variant_for_update(variant_id)
        if variant is None:
            raise NotFoundError("Variant was not found.")

        stock_delta = payload.stock - variant.stock
        for field in ("sku", "size", "color", "color_hex", "mrp", "price", "low_stock_threshold", "is_active"):
            setattr(variant, field, getattr(payload, field))
        variant.stock = payload.stock
        variant.version += 1

        if stock_delta != 0:
            self.products.add_movement(
                InventoryMovement(
                    variant_id=variant.id,
                    delta=stock_delta,
                    reason="admin_adjust",
                    balance_after=variant.stock,
                    note="Manual stock edit",
                    created_at=utcnow(),
                )
            )
        await self._recompute_stock_total(variant.product_id)
        await self.session.commit()
        return VariantOut.model_validate(variant)

    async def delete_variant(self, variant_id: int) -> None:
        variant = await self.products.get_variant_for_update(variant_id)
        if variant is None:
            raise NotFoundError("Variant was not found.")
        variant.deleted_at = utcnow()
        variant.is_active = False
        await self._recompute_stock_total(variant.product_id)
        await self.session.commit()

    # -- inventory -----------------------------------------------------------------------------

    async def adjust_inventory(self, variant_id: int, payload: InventoryAdjustIn, actor_user_id: int) -> VariantOut:
        variant = await self.products.get_variant_for_update(variant_id)
        if variant is None:
            raise NotFoundError("Variant was not found.")
        new_stock = variant.stock + payload.delta
        if new_stock < 0:
            raise ConflictError("This adjustment would take stock below zero.")

        was_available = variant.available > 0
        variant.stock = new_stock
        self.products.add_movement(
            InventoryMovement(
                variant_id=variant.id,
                delta=payload.delta,
                reason=payload.reason,
                balance_after=new_stock,
                actor_user_id=actor_user_id,
                note=payload.note,
                created_at=utcnow(),
            )
        )
        await self._recompute_stock_total(variant.product_id)
        await self.session.commit()

        if not was_available and variant.available > 0:
            # spec §9.8's StockReplenished event: notify anyone who asked for a back-in-stock
            # alert on this variant. No Celery here, so this runs inline in the request rather
            # than as a dispatched job — fine at this scale, a documented gap at real volume.
            product = await self.products.get_by_id(variant.product_id)
            if product is not None:
                notified = await StockAlertService(self.session).notify_restocked(
                    variant.id, product_title=product.title, product_slug=product.slug
                )
                if notified:
                    logger.info("stock_alerts_notified", variant_id=variant.id, count=notified)

        return VariantOut.model_validate(variant)

    async def low_stock(self, *, limit: int = 50) -> list[LowStockVariantOut]:
        variants = await self.products.low_stock_variants(limit=limit)
        return [
            LowStockVariantOut(
                variant_id=v.id,
                sku=v.sku,
                product_title=v.product.title,
                product_slug=v.product.slug,
                size=v.size,
                color=v.color,
                available=v.available,
                low_stock_threshold=v.low_stock_threshold,
            )
            for v in variants
        ]

    # -- lookups for the product form -----------------------------------------------------------

    async def list_brand_options(self) -> list[BrandOption]:
        return [BrandOption.model_validate(b) for b in await self.brands.list_all()]

    async def list_category_options(self) -> list[CategoryOption]:
        return [CategoryOption.model_validate(c) for c in await self.categories.list_all()]

    # -- internal --------------------------------------------------------------------------------

    async def _recompute_stock_total(self, product_id: int) -> None:
        # Flush first: get_by_id uses populate_existing=True (needed so its own eager-loaded
        # `.variants` collection refreshes instead of going stale — see the repository comment),
        # but that cuts both ways — it also overwrites any *uncommitted* in-memory change on an
        # identity-mapped variant back to its last-flushed DB value. Every caller here mutates a
        # variant (stock, deleted_at, is_active) immediately before recomputing, so without this
        # flush the recompute would silently discard that mutation before it's ever committed.
        await self.session.flush()
        product = await self.products.get_by_id(product_id)
        if product is None:
            return
        product.stock_total = sum(v.stock for v in product.variants if v.deleted_at is None)

    def _to_detail(self, product: Product) -> AdminProductDetail:
        return AdminProductDetail(
            id=product.id,
            slug=product.slug,
            title=product.title,
            subtitle=product.subtitle,
            description=product.description,
            brand_id=product.brand_id,
            category_id=product.category_id,
            gender=product.gender,
            material=product.material,
            base_color=product.base_color,
            currency=product.currency,
            mrp=product.mrp,
            price=product.price,
            status=product.status,
            is_deleted=product.deleted_at is not None,
            is_featured=product.is_featured,
            is_trending=product.is_trending,
            is_new_arrival=product.is_new_arrival,
            thumbnail_url=product.thumbnail_url,
            seo_title=product.seo_title,
            seo_description=product.seo_description,
            variants=[VariantOut.model_validate(v) for v in product.variants if v.deleted_at is None],
        )
