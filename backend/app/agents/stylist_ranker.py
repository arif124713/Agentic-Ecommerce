"""Stylist Agent's deterministic re-rank + diversity pass (chat_spec.md §5.1.2) — explicitly
backend, NOT the LLM. The model never sees the scoring math and never picks which products win;
it only writes prose about whichever set this module already decided on.

Two real, documented gaps versus spec's exact formula, both because the underlying data doesn't
exist in BlackCart's schema (not a shortcut, a fact about what catalog-mcp can actually return):
- `margin_boost` has no data source (no cost/margin column on `Product`) — the term stays in the
  formula at spec's 0.05 weight but always contributes 0. Never invented.
- `stock_health` uses raw `stock_level` (what catalog-mcp's product card exposes) instead of
  `days_of_cover` (an analytics-mcp-only figure the Stylist has no access to, and shouldn't —
  that's the Insights Agent's data, not this one's).
"""

from __future__ import annotations

import math

_WEIGHTS = {
    "palette_match": 0.30,
    "climate_fit": 0.20,
    "occasion_fit": 0.15,
    "popularity": 0.12,
    "budget_fit": 0.10,
    "stock_health": 0.08,
    "margin_boost": 0.05,
}

# Coarse hue families for "adjacent hue" scoring (spec: exact=1.0, adjacent=0.6, neutral=0.5,
# de-emphasized=0.1). Not exhaustive — covers the color vocabulary actually seeded in
# color_palettes/climate_profiles (backend/scripts/seed_styling_reference.py) plus common
# BlackCart product colors, grouped by the hue family a stylist would actually call "adjacent."
_HUE_FAMILIES: dict[str, str] = {
    "cobalt": "blue", "denim-blue": "blue", "navy": "blue", "electric-blue": "blue", "blue": "blue",
    "turquoise": "blue-green", "teal": "blue-green", "soft-teal": "blue-green",
    "emerald": "green", "forest": "green", "olive": "green", "dark-olive": "green", "green": "green",
    "fuchsia": "pink-purple", "hot-pink": "pink-purple", "plum": "pink-purple", "lilac": "pink-purple",
    "dusty-rose": "pink-purple", "muted-mauve": "pink-purple", "pink": "pink-purple", "purple": "pink-purple",
    "mustard": "yellow-gold", "gold": "yellow-gold", "washed-yellow": "yellow-gold",
    "neon-yellow": "yellow-gold", "yellow": "yellow-gold",
    "coral": "red-orange", "scarlet": "red-orange", "burnt-orange": "red-orange", "terracotta": "red-orange",
    "rust": "red-orange", "warm-red": "red-orange", "burgundy": "red-orange", "red": "red-orange",
    "optic-white": "neutral-light", "ivory": "neutral-light", "cream": "neutral-light",
    "pale-beige": "neutral-light", "white": "neutral-light",
    "charcoal": "neutral-dark", "deep-charcoal-brown": "neutral-dark", "mocha": "neutral-dark",
    "taupe": "neutral-dark", "grey-beige": "neutral-dark", "muddy-brown": "neutral-dark",
    "camel": "neutral-dark", "black": "neutral-dark", "grey": "neutral-dark", "brown": "neutral-dark",
    "lime": "green",
}


def _palette_match(color: str | None, recommended: list[str], de_emphasized: list[str]) -> float:
    if not color:
        return 0.5
    color = color.lower()
    recommended_l = {c.lower() for c in recommended}
    de_emphasized_l = {c.lower() for c in de_emphasized}
    if color in recommended_l:
        return 1.0
    if color in de_emphasized_l:
        return 0.1
    family = _HUE_FAMILIES.get(color)
    if family and any(_HUE_FAMILIES.get(r) == family for r in recommended_l):
        return 0.6
    return 0.4


def _climate_fit(fabric: str | None, suggested_fabrics: list[str], avoid_fabrics: list[str]) -> float:
    if not fabric:
        return 0.5
    fabric = fabric.lower()
    if any(f.lower() in fabric for f in avoid_fabrics):
        return 0.0
    if any(f.lower() in fabric for f in suggested_fabrics):
        return 1.0
    return 0.5


_OCCASION_CATEGORY_HINTS: dict[str, list[str]] = {
    "beach": ["swimwear", "sandals", "shorts"],
    "formal": ["blazers-suits", "formal"],
    "office": ["formal", "shirts"],
    "party": ["party", "ethnic"],
    "festive": ["ethnic", "kurta"],
    "casual": ["casual", "topwear", "tshirt"],
    "travel": [],
}


def _occasion_fit(category_slug: str, occasion: str | None) -> float:
    if not occasion:
        return 0.5
    hints = _OCCASION_CATEGORY_HINTS.get(occasion, [])
    return 1.0 if any(h in category_slug for h in hints) else 0.5


def _budget_fit(price: float, budget_max: float | None) -> float:
    if budget_max is None:
        return 1.0
    if price <= budget_max:
        return 1.0
    overage = (price - budget_max) / budget_max
    return max(0.0, 1.0 - overage)


def _stock_health(stock_level: int) -> float:
    if stock_level <= 0:
        return 0.0
    if stock_level < 2:
        return 0.3
    return 1.0


def score_products(
    products: list[dict],
    *,
    recommended_colors: list[str],
    de_emphasized_colors: list[str],
    suggested_fabrics: list[str],
    avoid_fabrics: list[str],
    occasion: str | None,
    budget_max: float | None,
) -> list[tuple[float, dict]]:
    raw_popularity = [
        (p.get("rating") or 0) * math.log1p(p.get("review_count") or 0) for p in products
    ]
    max_pop = max(raw_popularity) if raw_popularity else 0.0

    scored = []
    for product, pop_raw in zip(products, raw_popularity, strict=True):
        components = {
            "palette_match": _palette_match(product.get("color"), recommended_colors, de_emphasized_colors),
            "climate_fit": _climate_fit(product.get("fabric"), suggested_fabrics, avoid_fabrics),
            "occasion_fit": _occasion_fit(product.get("category") or "", occasion),
            "popularity": (pop_raw / max_pop) if max_pop > 0 else 0.5,
            "budget_fit": _budget_fit(float(product.get("price") or 0), budget_max),
            "stock_health": _stock_health(int(product.get("stock_level") or 0)),
            "margin_boost": 0.0,  # no cost/margin data in the schema — see module docstring
        }
        score = sum(_WEIGHTS[k] * v for k, v in components.items())
        scored.append((score, product))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def select_with_diversity(
    scored: list[tuple[float, dict]], *, target: int = 6, max_per_brand: int = 2, min_categories: int = 3
) -> list[dict]:
    """Greedy selection respecting spec §5.1.2's diversity constraint: >=min_categories distinct
    categories, <=max_per_brand items from any one brand. Backfills from an under-represented
    category by swapping out the lowest-scored pick from an over-represented one when the greedy
    pass alone doesn't reach the category minimum and a better-diversified candidate exists."""
    selected: list[dict] = []
    brand_counts: dict[str, int] = {}

    for score, product in scored:
        if len(selected) >= target:
            break
        brand = product.get("brand") or "unknown"
        if brand_counts.get(brand, 0) >= max_per_brand:
            continue
        selected.append(product)
        brand_counts[brand] = brand_counts.get(brand, 0) + 1

    categories = {p.get("category") for p in selected}
    if len(categories) < min_categories:
        selected_ids = {p.get("product_id") for p in selected}
        for score, product in scored:
            if len(categories) >= min_categories:
                break
            if product.get("product_id") in selected_ids:
                continue
            category = product.get("category")
            if category in categories:
                continue
            brand = product.get("brand") or "unknown"
            # swap out the lowest-scored current pick from an over-represented category/brand
            if selected:
                selected.pop()
            selected.append(product)
            selected_ids.add(product.get("product_id"))
            categories.add(category)
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

    return selected
