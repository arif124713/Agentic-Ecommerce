from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Brand, Category, Product
from app.models.discovery import SearchQuery


class SearchRepository:
    """Backs GET /search/suggest (spec §14.4): a single response with top products, brands,
    categories, and popular past queries — all cheap, indexed LIKE queries since there's no
    Elasticsearch completion suggester here (see done.MD stack deviations)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def suggest_products(self, q: str, limit: int = 5) -> list[Product]:
        like = f"%{q}%"
        stmt = (
            select(Product)
            .where(
                Product.status == "active",
                Product.deleted_at.is_(None),
                Product.title.ilike(like),
            )
            .order_by(Product.sold_count.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def suggest_brands(self, q: str, limit: int = 3) -> list[Brand]:
        like = f"%{q}%"
        stmt = (
            select(Brand)
            .where(Brand.is_active.is_(True), Brand.deleted_at.is_(None), Brand.name.ilike(like))
            .order_by(Brand.name)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def suggest_categories(self, q: str, limit: int = 3) -> list[Category]:
        like = f"%{q}%"
        stmt = (
            select(Category)
            .where(Category.is_active.is_(True), Category.deleted_at.is_(None), Category.name.ilike(like))
            .order_by(Category.sort_order, Category.name)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def popular_queries(self, q: str, limit: int = 4) -> list[str]:
        stmt = (
            select(SearchQuery.query, func.count().label("c"))
            .where(SearchQuery.query.ilike(f"{q}%"), SearchQuery.result_count > 0)
            .group_by(SearchQuery.query)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [r.query for r in rows]
