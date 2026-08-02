from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Brand, Category, InventoryMovement, Product, ProductVariant


class AdminProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_products(
        self, *, q: str | None, status: str | None, category_id: int | None, page: int, per_page: int
    ) -> tuple[list[Product], int]:
        stmt = select(Product).options(selectinload(Product.brand), selectinload(Product.category))
        if status:
            stmt = stmt.where(Product.status == status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Product.title.ilike(like), Product.slug.ilike(like)))
        if category_id:
            # Subtree match on the materialised path (same technique as the storefront's
            # ProductRepository) so picking a top-level category like "Men" still scopes to every
            # product under it, not just ones directly assigned to that exact row.
            category_path = (
                await self.session.execute(select(Category.path).where(Category.id == category_id))
            ).scalar_one_or_none()
            if category_path is None:
                stmt = stmt.where(Product.id == -1)  # no such category — match nothing
            else:
                stmt = stmt.join(Category, Product.category_id == Category.id).where(
                    (Category.path == category_path) | (Category.path.like(f"{category_path}/%"))
                )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Product.updated_at.desc()).offset((page - 1) * per_page).limit(per_page)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_id(self, product_id: int) -> Product | None:
        # populate_existing: callers often re-fetch the same product within one request after
        # mutating a related row (e.g. adding a variant) — without this, SQLAlchemy leaves the
        # already-identity-mapped product's `.variants` collection stale instead of refreshing it
        # (the same class of bug hit with carts/orders in Phases 2-3, see done.MD).
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.brand),
                selectinload(Product.category),
                selectinload(Product.variants),
                selectinload(Product.images),
            )
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, product: Product) -> None:
        self.session.add(product)

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(func.count()).where(Product.slug == slug)
        return (await self.session.execute(stmt)).scalar_one() > 0

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug).options(
            selectinload(Product.brand), selectinload(Product.category)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many_by_ids(self, product_ids: list[int]) -> list[Product]:
        stmt = select(Product).where(Product.id.in_(product_ids)).options(
            selectinload(Product.brand), selectinload(Product.category), selectinload(Product.variants)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all_for_export(self) -> list[Product]:
        stmt = (
            select(Product)
            .options(selectinload(Product.brand), selectinload(Product.category))
            .order_by(Product.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_variant_for_update(self, variant_id: int) -> ProductVariant | None:
        stmt = select(ProductVariant).where(ProductVariant.id == variant_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_variant(self, variant: ProductVariant) -> None:
        self.session.add(variant)

    def add_movement(self, movement: InventoryMovement) -> None:
        self.session.add(movement)

    async def low_stock_variants(self, *, limit: int = 50) -> list[ProductVariant]:
        stmt = (
            select(ProductVariant)
            .where(
                ProductVariant.is_active.is_(True),
                ProductVariant.deleted_at.is_(None),
                (ProductVariant.stock - ProductVariant.reserved) <= ProductVariant.low_stock_threshold,
            )
            .options(selectinload(ProductVariant.product))
            .order_by((ProductVariant.stock - ProductVariant.reserved).asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_low_stock(self) -> int:
        stmt = select(func.count()).where(
            ProductVariant.is_active.is_(True),
            ProductVariant.deleted_at.is_(None),
            (ProductVariant.stock - ProductVariant.reserved) <= ProductVariant.low_stock_threshold,
        )
        return (await self.session.execute(stmt)).scalar_one()


class AdminCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[Category]:
        stmt = select(Category).where(Category.deleted_at.is_(None)).order_by(Category.depth, Category.sort_order)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(func.lower(Category.name) == name.lower(), Category.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()


class AdminBrandRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[Brand]:
        stmt = select(Brand).where(Brand.deleted_at.is_(None)).order_by(Brand.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_name(self, name: str) -> Brand | None:
        stmt = select(Brand).where(func.lower(Brand.name) == name.lower(), Brand.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()
