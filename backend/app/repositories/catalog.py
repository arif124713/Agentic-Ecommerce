from decimal import Decimal

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.search_backend import get_search_backend
from app.models.catalog import Brand, Category, Product


def _tokens(q: str) -> list[str]:
    return [t for t in q.split() if len(t) >= 2] or [q]


def _token_condition(tokens: list[str], *, require_all: bool):
    """AND-of-tokens (precise: every word must appear somewhere) or OR-of-tokens (broadened:
    any word matches) across title/search_keywords. See done.MD for why this replaced a MySQL
    FULLTEXT ngram MATCH/AGAINST approach: empirically verified via curl that both NATURAL
    LANGUAGE and BOOLEAN phrase mode against an ngram(2)-tokenised index produced heavy false
    positives on this catalogue (e.g. "tee" matched ~3,900 of 8,103 products via shared 2-grams
    like "ee" with "Green"/"Sweet"), while plain LIKE gave the precise 3 titles actually
    containing "tee". The ft_products FULLTEXT index (spec §8.3/§14.2) is still declared on the
    model for schema fidelity and a future real-Elasticsearch swap; it just isn't queried."""
    conditions = [Product.title.ilike(f"%{t}%") | Product.search_keywords.ilike(f"%{t}%") for t in tokens]
    combined = conditions[0]
    for c in conditions[1:]:
        combined = (combined & c) if require_all else (combined | c)
    return combined


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _category_subtree_filter(self, category_slug: str) -> ColumnElement[bool]:
        """Match the category itself and all descendants via the materialised path (spec §8.3)."""
        stmt = select(Category.path).where(Category.slug == category_slug)
        path = (await self.session.execute(stmt)).scalar_one_or_none()
        if path is None:
            return Category.id == -1  # no such category — match nothing
        return (Category.path == path) | (Category.path.like(f"{path}/%"))

    async def get_by_id(self, product_id: int) -> Product | None:
        """Plain fetch, no eager loads — for callers (e.g. review aggregate recompute) that only
        need to read/write scalar columns, not the brand/category/images/variants graph."""
        return await self.session.get(Product, product_id)

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = (
            select(Product)
            .where(Product.slug == slug, Product.deleted_at.is_(None))
            .options(
                selectinload(Product.brand),
                selectinload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
    ) -> tuple[list[Product], int, bool]:
        """Returns (products, total, used_fallback). When q is given, tries a precise
        AND-of-tokens match first; a zero-result hit broadens to an OR-of-tokens match instead
        of showing a dead end (spec §14.3's "fallback broadened query")."""
        sort_map: dict[str, ColumnElement] = {
            "price": Product.price.asc(),
            "-price": Product.price.desc(),
            "-rating": Product.rating_avg.desc(),
            "-created_at": Product.created_at.desc(),
            "-popularity": Product.sold_count.desc(),
        }
        category_filter = await self._category_subtree_filter(category_slug) if category_slug else None
        tokens = _tokens(q) if q else []

        # Real search (Algolia), scoped to the common "search box, default relevance" case — see
        # core/search_backend.py's docstring for exactly why non-default sorts stay on MySQL.
        if q and sort in ("-popularity", "relevance"):
            search_backend = get_search_backend()
            if search_backend is not None:
                return await self._list_products_via_search_backend(
                    search_backend,
                    category_slug=category_slug,
                    brand_slugs=brand_slugs,
                    price_min=price_min,
                    price_max=price_max,
                    gender=gender,
                    q=q,
                    page=page,
                    per_page=per_page,
                )

        async def run(*, require_all: bool) -> tuple[list[Product], int]:
            stmt = (
                select(Product)
                .where(Product.status == "active", Product.deleted_at.is_(None))
                .options(selectinload(Product.brand))
            )
            if category_slug:
                assert category_filter is not None  # set above precisely when category_slug is truthy
                stmt = stmt.join(Category, Product.category_id == Category.id).where(category_filter)
            if brand_slugs:
                stmt = stmt.join(Brand, Product.brand_id == Brand.id).where(Brand.slug.in_(brand_slugs))
            if price_min is not None:
                stmt = stmt.where(Product.price >= price_min)
            if price_max is not None:
                stmt = stmt.where(Product.price <= price_max)
            if gender:
                stmt = stmt.where(Product.gender == gender)
            if q:
                stmt = stmt.where(_token_condition(tokens, require_all=require_all))

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await self.session.execute(count_stmt)).scalar_one()

            if q and sort in ("-popularity", "relevance"):
                # Cheap relevance proxy: an exact/prefix title match outranks a match buried in
                # search_keywords or mid-title, then break ties by popularity.
                relevance = case((Product.title.ilike(f"{q}%"), 1), else_=0)
                stmt = stmt.order_by(relevance.desc(), Product.sold_count.desc())
            else:
                stmt = stmt.order_by(sort_map.get(sort, Product.sold_count.desc()))
            stmt = stmt.offset((page - 1) * per_page).limit(per_page)

            result = await self.session.execute(stmt)
            return list(result.scalars().all()), total

        if q:
            products, total = await run(require_all=True)
            if total == 0:
                products, total = await run(require_all=False)
                return products, total, True
            return products, total, False

        products, total = await run(require_all=False)
        return products, total, False

    async def _list_products_via_search_backend(
        self,
        search_backend,
        *,
        category_slug: str | None,
        brand_slugs: list[str] | None,
        price_min: Decimal | None,
        price_max: Decimal | None,
        gender: str | None,
        q: str,
        page: int,
        per_page: int,
    ) -> tuple[list[Product], int, bool]:
        category_path = None
        if category_slug:
            path_stmt = select(Category.path).where(Category.slug == category_slug)
            category_path = (await self.session.execute(path_stmt)).scalar_one_or_none()

        ids, total = await search_backend.search_products(
            q=q,
            category_path=category_path,
            brand_slugs=brand_slugs,
            price_min=float(price_min) if price_min is not None else None,
            price_max=float(price_max) if price_max is not None else None,
            gender=gender,
            page=page,
            per_page=per_page,
        )
        if not ids:
            return [], total, False

        # Algolia decides which products and in what order; MySQL still hydrates the actual rows
        # (brand relationship etc.) — re-sort by Algolia's ranking since IN(...) doesn't preserve
        # the input order.
        stmt = select(Product).where(Product.id.in_(ids)).options(selectinload(Product.brand))
        rows = {p.id: p for p in (await self.session.execute(stmt)).scalars().all()}
        products = [rows[i] for i in ids if i in rows]
        return products, total, False

    async def category_facets(self, category_slug: str | None) -> list[tuple[str, str, int, bool]]:
        """Sub-category navigation chips: the current category's children (drill-down), or —
        if it's a leaf with no children — its siblings, so a leaf page can still switch between
        neighbours. Returns (slug, name, product_count, is_current)."""
        if not category_slug:
            return []

        current = (
            await self.session.execute(
                select(Category.id, Category.parent_id).where(Category.slug == category_slug)
            )
        ).first()
        if current is None:
            return []

        children_stmt = (
            select(Category.id, Category.slug, Category.name)
            .where(Category.parent_id == current.id, Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.name)
        )
        children = (await self.session.execute(children_stmt)).all()
        active_slug = None

        if not children and current.parent_id is not None:
            children_stmt = (
                select(Category.id, Category.slug, Category.name)
                .where(Category.parent_id == current.parent_id, Category.is_active.is_(True))
                .order_by(Category.sort_order, Category.name)
            )
            children = (await self.session.execute(children_stmt)).all()
            active_slug = category_slug

        if not children:
            return []

        child_ids = [c.id for c in children]
        count_stmt = (
            select(Product.category_id, func.count(Product.id))
            .where(
                Product.category_id.in_(child_ids),
                Product.status == "active",
                Product.deleted_at.is_(None),
            )
            .group_by(Product.category_id)
        )
        counts: dict[int, int] = dict((await self.session.execute(count_stmt)).tuples().all())

        return [
            (c.slug, c.name, counts.get(c.id, 0), c.slug == active_slug)
            for c in children
            if counts.get(c.id, 0) > 0
        ]

    async def brand_facets(self, category_slug: str | None = None) -> list[tuple[str, int]]:
        stmt = (
            select(Brand.name, func.count(Product.id))
            .join(Product, Product.brand_id == Brand.id)
            .where(Product.status == "active", Product.deleted_at.is_(None))
        )
        if category_slug:
            stmt = stmt.join(Category, Product.category_id == Category.id).where(
                await self._category_subtree_filter(category_slug)
            )
        stmt = stmt.group_by(Brand.name).order_by(func.count(Product.id).desc()).limit(20)
        result = await self.session.execute(stmt)
        return list(result.tuples().all())

    async def similar(self, product: Product, limit: int = 8) -> list[Product]:
        """Spec §14.5's "Similar products" rail — same category, gender, and a ±40% price band
        instead of ES's more_like_this, then a broadened same-category-only retry if the band
        comes up empty (common in this catalogue's smaller sub-categories)."""

        async def query(*, price_band: bool) -> list[Product]:
            stmt = (
                select(Product)
                .where(
                    Product.id != product.id,
                    Product.category_id == product.category_id,
                    Product.status == "active",
                    Product.deleted_at.is_(None),
                )
                .options(selectinload(Product.brand))
                .order_by(Product.rating_avg.desc(), Product.sold_count.desc())
                .limit(limit)
            )
            if price_band:
                stmt = stmt.where(
                    Product.price >= product.price * Decimal("0.6"),
                    Product.price <= product.price * Decimal("1.4"),
                )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        products = await query(price_band=True)
        if not products:
            products = await query(price_band=False)
        return products

    async def frequently_bought_with(self, product_id: int, limit: int = 4) -> list[Product]:
        """Spec §14.5's "Frequently bought together" — co-occurrence counts from order_items,
        computed on-demand rather than a nightly Celery job into product_affinity (no Celery here;
        see done.MD). With only a handful of demo orders this will often be sparse, which is
        honest given the actual data rather than fabricated."""
        from app.models.commerce import OrderItem  # local import: avoids a catalog->commerce cycle

        co_order_ids = select(OrderItem.order_id).where(OrderItem.product_id == product_id)
        stmt = (
            select(Product, func.count(OrderItem.id).label("cnt"))
            .join(OrderItem, OrderItem.product_id == Product.id)
            .where(
                OrderItem.order_id.in_(co_order_ids),
                Product.id != product_id,
                Product.status == "active",
                Product.deleted_at.is_(None),
            )
            .options(selectinload(Product.brand))
            .group_by(Product.id)
            .order_by(func.count(OrderItem.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]


class CategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.is_active.is_(True), Category.deleted_at.is_(None))
            .order_by(Category.depth, Category.sort_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug, Category.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class BrandRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[Brand]:
        stmt = (
            select(Brand)
            .where(Brand.is_active.is_(True), Brand.deleted_at.is_(None))
            .order_by(Brand.sort_order, Brand.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
