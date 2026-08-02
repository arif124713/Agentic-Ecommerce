"""Real search, on top of Algolia (spec §14.1 wants Elasticsearch; Vercel's Marketplace has no
plain-ES product, so Algolia fills the "real search engine, not MySQL LIKE" role — see done.MD for
why Algolia was chosen over Amazon OpenSearch Serverless / a separate Bonsai account).

Deliberately scoped down, matching this project's usual pattern:
- Algolia is only reached for the **q-given, default-sort** path (`sort in ("-popularity",
  "relevance")`). Plain category/brand browsing with no search text stays on MySQL — it's already
  fast and correct, and paying Algolia's network round-trip for it would be pure overhead. A
  search combined with an explicit non-default sort (price/rating/newest) also stays on MySQL:
  Algolia's own idiomatic way to support alternate sort orders is per-sort *replica indices*,
  which is real infrastructure this pass doesn't build — a documented gap, not a silent one.
- MySQL stays the single source of truth for product data. Algolia only returns which product IDs
  match and in what order; the actual `Product` rows are always re-fetched from MySQL for
  hydration (brand/category/images), so `to_product_card()` and friends never need a second,
  Algolia-shaped code path.
- Only ever-active, non-deleted products are indexed at all — matching the MySQL repository's own
  `status='active' AND deleted_at IS NULL` filter. A product leaving that state is *removed* from
  the index rather than indexed-and-filtered.

Record shape and category filtering follow the Algolia data-modeling skill's guidance: one record
per product (this project's PLP/PDP are already product-level, not variant-level — matches spec
§14.2's array-typed `colors`/`sizes` fields), a stable `objectID` (the immutable product id, never
a mutable field like slug/title), and `category_paths` denormalized to every ancestor path of the
product's own category (computed from the materialised `Category.path` string, no extra queries)
so a subtree filter like "everything under /men" is a single exact-match facet filter rather than
a query-time prefix scan Algolia's filter syntax doesn't support anyway.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from algoliasearch.search.client import SearchClient

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.models.catalog import Product

_INDEX_NAME = "products"

_INDEX_SETTINGS = {
    # Priority order, not weights — Algolia ranks by how many/which searchable attributes matched,
    # in the order they're listed here, before falling through to customRanking. Mirrors spec
    # §14.3's multi_match weighting (title > brand/category > description) without literal scores.
    "searchableAttributes": ["title", "brand", "category_path", "search_keywords", "unordered(description)"],
    "attributesForFaceting": ["brand_slug", "category_paths", "gender", "colors", "sizes", "in_stock"],
    # Business tie-breakers after text relevance (spec's `rank_feature` boost on popularity) —
    # sold_count first, rating as the secondary tiebreak. No bucketing: at this catalogue's size
    # (~8k products) precision isn't the noisy-ranking problem the data-modeling skill warns about.
    "customRanking": ["desc(sold_count)", "desc(rating_avg)"],
    # Verified live against the real catalogue: "nike" typo-tolerance-matched "nice" inside the
    # generic boilerplate filler text nearly every product's description shares ("...will be a
    # nice addition to your closet...") and, absent any genuinely better match, those description-
    # only hits dominated the top of results — the same class of false positive this project
    # already hit and fixed for MySQL's FULLTEXT ngram parser (see repositories/catalog.py).
    # Typo tolerance stays on for title/brand/category/search_keywords, where it's actually doing
    # its job (e.g. "shrit" -> "shirt"); description is lowest-priority anyway (last in
    # searchableAttributes, `unordered()`), so this only removes its worst failure mode.
    "disableTypoToleranceOnAttributes": ["description"],
}

# Fashion vocabulary from spec §14.2. Algolia synonyms are bidirectional by default (`type:
# "synonym"`), matching the spec's `⇄` notation directly — no need for one-way `onewaysynonym`.
_SYNONYMS = [
    {"objectID": "syn-tee", "type": "synonym", "synonyms": ["tee", "t-shirt", "tshirt"]},
    {"objectID": "syn-trousers", "type": "synonym", "synonyms": ["trousers", "pants"]},
    {"objectID": "syn-kurti", "type": "synonym", "synonyms": ["kurti", "kurta"]},
    {"objectID": "syn-sneakers", "type": "synonym", "synonyms": ["sneakers", "trainers", "shoes"]},
    {"objectID": "syn-frock", "type": "synonym", "synonyms": ["frock", "dress"]},
]


class SearchBackend(Protocol):
    async def search_products(
        self,
        *,
        q: str,
        category_path: str | None,
        brand_slugs: list[str] | None,
        price_min: float | None,
        price_max: float | None,
        gender: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[int], int]:
        """Returns (product_ids in ranked order, total matches)."""
        ...

    async def suggest_products(self, q: str, limit: int) -> list[int]:
        """Returns product_ids for autocomplete — typo-tolerant, unlike the MySQL ILIKE fallback."""
        ...


def _category_ancestor_paths(path: str) -> list[str]:
    parts = [p for p in path.split("/") if p]
    return ["/" + "/".join(parts[: i + 1]) for i in range(len(parts))]


def product_to_record(product: Product) -> dict:
    """Requires `product.brand`, `product.category`, and `product.variants` already loaded —
    callers use the same `selectinload`s as `ProductRepository.get_by_slug`."""
    active_variants = [v for v in product.variants if v.is_active]
    colors = sorted({v.color for v in active_variants if v.color})
    sizes = sorted({v.size for v in active_variants if v.size})
    in_stock = any((v.stock - v.reserved) > 0 for v in active_variants)

    return {
        "objectID": str(product.id),
        "id": product.id,
        "slug": product.slug,
        "title": product.title,
        "description": (product.description or "")[:2000],
        "search_keywords": product.search_keywords or "",
        "brand": product.brand.name,
        "brand_slug": product.brand.slug,
        "category_path": product.category.path,
        "category_paths": _category_ancestor_paths(product.category.path),
        "gender": product.gender,
        "colors": colors,
        "sizes": sizes,
        "material": product.material,
        "price": float(product.price),
        "mrp": float(product.mrp),
        "discount_percent": float(product.discount_percent),
        "rating_avg": float(product.rating_avg) if product.rating_avg is not None else 0.0,
        "rating_count": product.rating_count,
        "sold_count": product.sold_count,
        "in_stock": in_stock,
        "status": product.status,
        "thumbnail_url": product.thumbnail_url,
        "currency": product.currency,
        "published_at": int(product.published_at.timestamp()) if product.published_at else None,
    }


def _build_filters(
    *,
    category_path: str | None,
    brand_slugs: list[str] | None,
    price_min: float | None,
    price_max: float | None,
    gender: str | None,
) -> str:
    clauses = []
    if category_path:
        clauses.append(f'category_paths:"{category_path}"')
    if brand_slugs:
        brand_clause = " OR ".join(f'brand_slug:"{slug}"' for slug in brand_slugs)
        clauses.append(f"({brand_clause})")
    if gender:
        clauses.append(f'gender:"{gender}"')
    if price_min is not None:
        clauses.append(f"price >= {price_min}")
    if price_max is not None:
        clauses.append(f"price <= {price_max}")
    return " AND ".join(clauses)


class AlgoliaSearchBackend:
    def __init__(self) -> None:
        settings = get_settings()
        missing = [
            name
            for name, value in (
                ("ALGOLIA_APP_ID", settings.algolia_app_id),
                ("ALGOLIA_WRITE_API_KEY", settings.algolia_write_api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing settings for the algolia search backend: {', '.join(missing)}")
        # The write key can do everything the search key can (and more) — used everywhere here
        # rather than juggling two clients, since this backend is only ever used server-side.
        self._client = SearchClient(settings.algolia_app_id, settings.algolia_write_api_key)

    async def search_products(
        self,
        *,
        q: str,
        category_path: str | None = None,
        brand_slugs: list[str] | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        gender: str | None = None,
        page: int = 1,
        per_page: int = 24,
    ) -> tuple[list[int], int]:
        params: dict = {
            "query": q,
            "page": max(0, page - 1),
            "hitsPerPage": per_page,
            "attributesToRetrieve": ["objectID"],
        }
        filters = _build_filters(
            category_path=category_path,
            brand_slugs=brand_slugs,
            price_min=price_min,
            price_max=price_max,
            gender=gender,
        )
        if filters:
            params["filters"] = filters

        response = await self._client.search_single_index(index_name=_INDEX_NAME, search_params=params)
        ids = [int(hit.object_id) for hit in response.hits]
        return ids, response.nb_hits or 0

    async def suggest_products(self, q: str, limit: int = 5) -> list[int]:
        params = {"query": q, "hitsPerPage": limit, "attributesToRetrieve": ["objectID"]}
        response = await self._client.search_single_index(index_name=_INDEX_NAME, search_params=params)
        return [int(hit.object_id) for hit in response.hits]

    async def index_products(self, products: list[Product]) -> None:
        active = [p for p in products if p.status == "active" and p.deleted_at is None]
        inactive_ids = [str(p.id) for p in products if p not in active]
        if active:
            await self._client.save_objects(
                index_name=_INDEX_NAME,
                objects=[product_to_record(p) for p in active],
                wait_for_tasks=True,
            )
        if inactive_ids:
            await self._client.delete_objects(index_name=_INDEX_NAME, object_ids=inactive_ids, wait_for_tasks=True)

    async def delete_products(self, product_ids: list[int]) -> None:
        if product_ids:
            await self._client.delete_objects(
                index_name=_INDEX_NAME, object_ids=[str(i) for i in product_ids], wait_for_tasks=True
            )

    async def configure_index(self) -> None:
        """Idempotent — safe to re-run. Called once from scripts/reindex_algolia.py, not on every
        request; index-wide settings/synonyms don't change per-write."""
        await self._client.set_settings(index_name=_INDEX_NAME, index_settings=_INDEX_SETTINGS)
        await self._client.save_synonyms(index_name=_INDEX_NAME, synonym_hit=_SYNONYMS, replace_existing_synonyms=True)

    async def close(self) -> None:
        """Only meaningful for short-lived callers (scripts) — the cached instance behind
        `get_search_backend()` deliberately stays open for the life of the process."""
        await self._client.close()


@lru_cache
def get_search_backend() -> AlgoliaSearchBackend | None:
    """None means "use MySQL" — callers branch on this rather than getting a MySQL implementation
    of the same Protocol, since the MySQL path already lives in ProductRepository/SearchRepository
    and doesn't need a second, parallel implementation of itself.

    Cached (mirrors `get_settings()`'s own `@lru_cache`): `SearchClient` holds an aiohttp session
    meant to be reused across requests, not opened and leaked on every call — Vercel's Fluid
    Compute keeps a function instance warm across invocations, so one client per process is both
    correct and the efficient choice, not just a shortcut."""
    if get_settings().search_backend == "algolia":
        return AlgoliaSearchBackend()
    return None


async def sync_products_to_search(products: list[Product]) -> None:
    backend = get_search_backend()
    if backend is not None:
        await backend.index_products(products)


async def remove_products_from_search(product_ids: list[int]) -> None:
    backend = get_search_backend()
    if backend is not None:
        await backend.delete_products(product_ids)
