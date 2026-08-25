"""catalog-mcp (chat_spec.md §4.1). Read-only over the product catalog. Wraps the SAME MySQL
models/queries the storefront itself uses — no parallel data path.

`search_products` deliberately does NOT go through `app.core.search_backend`'s Algolia client, even
though the Stylist now does send free-text `q` (see that param's own docstring — added after a real
report that results weren't varying with the specific problem described, only destination/skin-tone/
gender/budget): Algolia's index isn't configured with fabric/occasion/climate facets, and `q` here
reuses the exact same broadened OR-of-tokens title/search_keywords match
(`app.repositories.catalog._token_condition`) the plain-MySQL storefront search path already uses,
combined with the destination/palette-derived structured filters rather than replacing them. Going
straight to MySQL here matches the app's own existing routing decision, not a new one.

**Documented gap**: `occasion` and `climate` are accepted (matching the spec's inputSchema so a
future migration can wire them up) but currently NOOP — `Product` has no `occasion_tags`/
`climate_tags` columns (unlike chat_spec.md §10's assumed schema). Filtering instead happens on
`categories`/`colors`/`fabrics`/`gender`/price, which cover the same intent through what data
actually exists (e.g. a "beach" occasion is expressed by which categories/fabrics the Stylist's
slot extraction + climate_profiles fixture pick, not a raw tag match here).
"""

from __future__ import annotations

from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.mcp.common import primary_session, to_jsonable
from app.models.catalog import Category, Product, ProductVariant
from app.models.styling import ClimateProfile, ColorPalette, DestinationAlias
from app.repositories.catalog import ProductRepository, _token_condition, _tokens

mcp = FastMCP(name="catalog-mcp", instructions="Read-only product catalog search and detail lookup.")

_SKIN_LIGHTENING_BLOCKLIST = ["fairness", "whitening", "skin lightening", "de-tan", "brightening cream", "bleach cream"]


def _product_card(product: Product) -> dict:
    settings = get_settings()
    variants = [v for v in product.variants if v.is_active]
    in_stock_variants = [v for v in variants if (v.stock - v.reserved) > 0]
    sizes = sorted({v.size for v in variants if v.size})
    # `variant_id` here is the REAL numeric ProductVariant.id, not a SKU — the frontend's cart API
    # (POST /cart/items) takes exactly this id, per app/schemas/cart.py. ProductVariant has no
    # public_id (only Product does), so unlike product_id, this is the raw internal id by
    # necessity, not a documented deviation from this project's own enumeration-resistance
    # convention — variant ids were never treated as sensitive anywhere else in this codebase
    # either (frontend/src/types/catalog.ts's own ProductVariant.id is the same raw int).
    return {
        "product_id": product.public_id,
        "sku": variants[0].sku if variants else None,
        "title": product.title,
        "brand": product.brand.name,
        "category": product.category.slug,
        "color": product.base_color,
        "fabric": product.material,
        "price": product.price,
        "compare_at_price": product.mrp if product.mrp > product.price else None,
        "currency": product.currency,
        "image_url": product.thumbnail_url,
        "product_url": f"{settings.app_base_url}/p/{product.slug}",
        "rating": product.rating_avg,
        "review_count": product.review_count,
        "in_stock": product.stock_total > 0,
        "available_sizes": sizes,
        "stock_level": product.stock_total,
        "default_variant_id": in_stock_variants[0].id if in_stock_variants else None,
        "variants": [
            {"variant_id": v.id, "size": v.size, "color": v.color, "in_stock": (v.stock - v.reserved) > 0}
            for v in variants
        ],
        "tags": [],
    }


@mcp.tool()
async def search_products(
    limit: int,
    q: str | None = None,
    categories: list[str] | None = None,
    colors: list[str] | None = None,
    exclude_colors: list[str] | None = None,
    fabrics: list[str] | None = None,
    gender: str | None = None,
    occasion: str | None = None,
    climate: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    in_stock_only: bool = True,
    skin_tone_context: bool = False,
) -> dict:
    """Faceted product search. Returns ranked products with images and prices. Always request
    limit>=8 so the caller's own ranker has headroom to return at least 5 after filtering.

    `q`: free-text terms describing the actual need behind the request (e.g. "wedding guest",
    "trekking jacket", "office interview") — matched (broadened OR-of-tokens, any word) against
    title/search_keywords, the same matching this catalog's own storefront search uses (see
    `app.repositories.catalog._token_condition`). This is what makes results vary with the specific
    problem being solved rather than just destination/skin-tone/gender/budget; omit it for a pure
    facet browse.

    skin_tone_context=true (set whenever the caller derived `colors` from a skin-tone palette,
    i.e. get_color_palette was used this turn): excludes skin-lightening/whitening/fairness/
    brightening-cream products by construction (spec §9.4 — a hard category blocklist, never left
    to the model). BlackCart's current catalog is apparel-only and has none of these, but the
    filter runs regardless so it's real protection the moment such a product ever exists, not
    theater."""
    limit = max(1, min(limit, 30))
    async with primary_session() as session:
        stmt = (
            select(Product)
            .where(Product.status == "active", Product.deleted_at.is_(None))
            .options(selectinload(Product.brand), selectinload(Product.category), selectinload(Product.variants))
        )

        if q and q.strip():
            stmt = stmt.where(_token_condition(_tokens(q.strip()), require_all=False))

        if categories:
            repo = ProductRepository(session)
            category_clauses = [await repo._category_subtree_filter(slug) for slug in categories]
            combined = category_clauses[0]
            for clause in category_clauses[1:]:
                combined = combined | clause
            stmt = stmt.join(Category, Product.category_id == Category.id).where(combined)

        if gender:
            stmt = stmt.where(Product.gender == gender)
        if price_min is not None:
            stmt = stmt.where(Product.price >= Decimal(str(price_min)))
        if price_max is not None:
            stmt = stmt.where(Product.price <= Decimal(str(price_max)))
        if in_stock_only:
            stmt = stmt.where(Product.stock_total > 0)
        if fabrics:
            fabric_clause: ColumnElement[bool] = Product.material.ilike(f"%{fabrics[0]}%")
            for fabric in fabrics[1:]:
                fabric_clause = fabric_clause | Product.material.ilike(f"%{fabric}%")
            stmt = stmt.where(fabric_clause)
        if colors:
            stmt = stmt.where(func.lower(Product.base_color).in_({c.lower() for c in colors}))
        if exclude_colors:
            stmt = stmt.where(func.lower(Product.base_color).notin_({c.lower() for c in exclude_colors}))
        if skin_tone_context:
            for term in _SKIN_LIGHTENING_BLOCKLIST:
                stmt = stmt.where(~Product.title.ilike(f"%{term}%"))

        if q and q.strip():
            # Title-prefix matches first (closest to what the user actually asked for), then fall
            # back to popularity within each relevance tier — otherwise a broadened OR-of-tokens
            # match would still just re-sort back to "same best-sellers" order.
            relevance = case((Product.title.ilike(f"{q.strip()}%"), 1), else_=0)
            stmt = stmt.order_by(relevance.desc(), Product.sold_count.desc()).limit(limit)
        else:
            stmt = stmt.order_by(Product.sold_count.desc()).limit(limit)
        products = list((await session.execute(stmt)).scalars().all())

        return to_jsonable({"count": len(products), "products": [_product_card(p) for p in products]})


@mcp.tool()
async def get_product(product_id: str) -> dict:
    """Full detail for one product, addressed by its public product_id (not the internal
    numeric id)."""
    async with primary_session() as session:
        stmt = (
            select(Product)
            .where(Product.public_id == product_id, Product.deleted_at.is_(None))
            .options(selectinload(Product.brand), selectinload(Product.category), selectinload(Product.variants))
        )
        product = (await session.execute(stmt)).scalar_one_or_none()
        if product is None:
            return {"error": "not_found", "product_id": product_id}
        card = _product_card(product)
        card["description"] = product.description
        card["variants"] = [
            {
                "variant_id": v.sku,
                "size": v.size,
                "color": v.color,
                "price": v.price,
                "in_stock": (v.stock - v.reserved) > 0,
                "stock_level": v.stock - v.reserved,
            }
            for v in product.variants
            if v.is_active
        ]
        return to_jsonable(card)


@mcp.tool()
async def check_availability(sku: str) -> dict:
    """Live stock for a single variant, addressed by SKU."""
    async with primary_session() as session:
        stmt = select(ProductVariant).where(ProductVariant.sku == sku)
        variant = (await session.execute(stmt)).scalar_one_or_none()
        if variant is None:
            return {"error": "not_found", "sku": sku}
        available = variant.stock - variant.reserved
        return to_jsonable(
            {
                "sku": variant.sku,
                "in_stock": available > 0,
                "stock_level": max(available, 0),
                "low_stock": 0 < available <= variant.low_stock_threshold,
            }
        )


@mcp.tool()
async def get_color_palette(depth: str, undertone: str = "unknown") -> dict:
    """Returns recommended and de-emphasized color slugs for a skin tone. Use this before
    search_products whenever the user mentions their complexion. Deterministic lookup — never
    invent a palette outside what this tool returns."""
    async with primary_session() as session:
        stmt = select(ColorPalette).where(ColorPalette.depth == depth, ColorPalette.undertone == undertone)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None and undertone != "unknown":
            stmt = select(ColorPalette).where(ColorPalette.depth == depth, ColorPalette.undertone == "unknown")
            row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return {"error": "unknown_depth", "depth": depth}
        return to_jsonable(
            {
                "depth": row.depth,
                "undertone": row.undertone,
                "recommended": row.recommended,
                "de_emphasized": row.de_emphasized,
                "rationale": row.rationale,
            }
        )


@mcp.tool()
async def get_climate_profile(destination: str) -> dict:
    """Destination slug/free-text → climate archetype + typical categories/fabrics. Resolves via
    a destination_aliases lookup (case-insensitive) before falling back to a generic profile."""
    normalized = destination.strip().lower()
    async with primary_session() as session:
        alias_stmt = (
            select(ClimateProfile)
            .join(DestinationAlias, DestinationAlias.climate_profile_id == ClimateProfile.id)
            .where(DestinationAlias.alias == normalized)
        )
        profile = (await session.execute(alias_stmt)).scalar_one_or_none()
        if profile is None:
            slug_stmt = select(ClimateProfile).where(ClimateProfile.slug == normalized)
            profile = (await session.execute(slug_stmt)).scalar_one_or_none()
        if profile is None:
            return {
                "destination": destination,
                "resolved_slug": None,
                "climate": "temperate",
                "assumption": (
                    f"Couldn't resolve '{destination}' to a known destination — assuming "
                    "temperate conditions."
                ),
                "terrain": [],
                "typical_occasions": [],
                "suggested_categories": [],
                "suggested_fabrics": [],
                "avoid_fabrics": [],
            }
        return to_jsonable(
            {
                "destination": profile.display_name,
                "resolved_slug": profile.slug,
                "lat": profile.lat,
                "lon": profile.lon,
                "climate": profile.climate,
                "terrain": profile.terrain,
                "typical_occasions": profile.typical_occasions,
                "suggested_categories": profile.suggested_categories,
                "suggested_fabrics": profile.suggested_fabrics,
                "avoid_fabrics": profile.avoid_fabrics,
                # What the place actually looks like and what's culturally normal to wear there —
                # this is what lets the Stylist reason like an actual stylist instead of a
                # weather report with products attached (see app/agents/stylist.py's prose call).
                "visual_character": profile.visual_character,
                "style_notes": profile.style_notes,
            }
        )
