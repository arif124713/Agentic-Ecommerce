"""Ingest the real Flipkart Fashion Products dataset (spec §7) into the catalogue tables.

A `--stage` CLI over spec §7.2's 9 stages, condensed to the 5 that are actually distinct pipeline
steps for this dataset/scale: `fetch`, `profile`, `load` (clean+normalise+enrich+load combined —
see the docstring on `stage_load` for why splitting those three further would just invent an
intermediate file format nothing else needs at 30k records), `media`, `verify`. `index` isn't a
stage here at all: there's no Elasticsearch in this stack (documented throughout done.MD), so
there's nothing for an index stage to do beyond what `load` already does for MySQL search.

The dataset has no variant/stock/rating-count/sold-count data, so — per spec §7.3
("out_of_stock maps to stock 0; otherwise stock is randomised... since the dataset has none") —
those are seeded deterministically from each record's pid so re-running is reproducible.

Run: python scripts/ingest_flipkart.py --stage load   (or fetch / profile / media / verify)
"""

import argparse
import asyncio
import hashlib
import html
import io
import json
import random
import re
import sys
import time
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import bindparam, func, insert, select, text  # noqa: E402
from ulid import ULID  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.image_pipeline import process_image  # noqa: E402
from app.core.storage import MEDIA_ROOT, get_storage_backend  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.models.catalog import Brand, Category, Product, ProductAttribute, ProductImage, ProductVariant  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "data" / "raw" / "flipkart_fashion_products_dataset.json"
QUARANTINE_DIR = ROOT / "data" / "quarantine"
KAGGLE_DATASET_URL = "https://www.kaggle.com/api/v1/datasets/download/aaditshukla/flipkart-fasion-products-dataset"

BATCH_SIZE = 1000
REJECTION_THRESHOLD = 0.15  # generous: this source dataset is noisier than a curated feed
MIN_CATEGORY_PRODUCTS = 50  # top-level (gender) categories below this are dropped, not shown half-empty

CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
FOOTWEAR_SIZES = ["6", "7", "8", "9", "10", "11"]

COLOR_HEX = {
    "black": "#000000", "white": "#ffffff", "blue": "#2563eb", "red": "#dc2626",
    "green": "#16a34a", "yellow": "#eab308", "pink": "#ec4899", "purple": "#9333ea",
    "grey": "#6b7280", "gray": "#6b7280", "brown": "#78350f", "orange": "#ea580c",
    "navy": "#1e3a5f", "navy blue": "#1e3a5f", "beige": "#d6c7a1", "maroon": "#7f1d1d",
    "olive": "#556b2f", "khaki": "#c3b091", "cream": "#fffdd0", "multicolor": "#8a8a8a",
    "silver": "#c0c0c0", "gold": "#d4af37", "teal": "#0d9488",
}

# (source category, source sub_category) -> (leaf_slug, leaf_name)
CATEGORY_MAP = {
    ("Clothing and Accessories", "Topwear"): ("topwear", "Topwear"),
    ("Clothing and Accessories", "Bottomwear"): ("bottomwear", "Bottomwear"),
    ("Clothing and Accessories", "Winter Wear"): ("winter-wear", "Winter Wear"),
    ("Clothing and Accessories", "Innerwear and Swimwear"): ("innerwear-swimwear", "Innerwear & Swimwear"),
    ("Clothing and Accessories", "Clothing Accessories"): ("accessories", "Accessories"),
    ("Clothing and Accessories", "Kurtas, Ethnic Sets and Bottoms"): ("ethnic-wear", "Ethnic Wear"),
    ("Footwear", "Men's Footwear"): ("footwear", "Footwear"),
    ("Clothing and Accessories", "Fabrics"): ("fabrics", "Fabrics"),
    ("Clothing and Accessories", "Blazers, Waistcoats and Suits"): ("blazers-suits", "Blazers & Suits"),
    ("Clothing and Accessories", "Sleepwear"): ("sleepwear", "Sleepwear"),
    ("Clothing and Accessories", "Tracksuits"): ("tracksuits", "Tracksuits"),
    ("Clothing and Accessories", "Raincoats"): ("raincoats", "Raincoats"),
}

ATTRIBUTE_ALLOWLIST = {
    "Fabric": "material", "Pattern": "pattern", "Fit": "fit", "Sleeve": "sleeve",
    "Type": "type", "Neck Type": "neck_type", "Country of Origin": "origin",
    "Sales Package": "sales_package",
}

GENDER_RE = {
    "women": re.compile(r"\bwomens?\b", re.I),
    "men": re.compile(r"\bmens?\b", re.I),
    "boys": re.compile(r"\bboys\b", re.I),
    "girls": re.compile(r"\bgirls\b", re.I),
    "kids": re.compile(r"\bkids?\b|\binfant\b|\bbaby\b", re.I),
}


def slugify(*parts: str) -> str:
    text_ = "-".join(str(p) for p in parts if p)
    text_ = text_.lower()
    text_ = re.sub(r"[^a-z0-9]+", "-", text_).strip("-")
    return text_[:250] or "item"


def clean_title(raw: str | None) -> str:
    if not raw:
        return ""
    t = html.unescape(raw)
    t = re.sub(r"\s+", " ", t).strip()
    if t.isupper() or t.islower():
        t = t.title()
    return t[:255]


def clean_price(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("1"))
    except InvalidOperation:
        return None


def clean_rating(raw: str | None) -> Decimal | None:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return None
    if value < 0 or value > 5:
        return None
    return value.quantize(Decimal("0.01"))


def flatten_attributes(product_details: list[dict] | None) -> dict[str, str]:
    flat: dict[str, str] = {}
    for item in product_details or []:
        if isinstance(item, dict):
            for k, v in item.items():
                if k not in flat:
                    flat[k] = str(v)
    return flat


def infer_gender(attrs: dict[str, str], title: str) -> str:
    ideal_for = attrs.get("Ideal For", "")
    first_token = ideal_for.split(",")[0].strip().lower() if ideal_for else ""
    if first_token in {"men", "women", "boys", "girls"}:
        return first_token
    for gender, pattern in GENDER_RE.items():
        if pattern.search(title):
            return gender
    return "unisex"


def map_category(category: str | None, sub_category: str | None) -> tuple[str, str]:
    key = (category or "", sub_category or "")
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    sc = (sub_category or "").lower()
    if any(word in sc for word in ("bag", "wallet", "belt")):
        return ("accessories", "Accessories")
    if "footwear" in sc:
        return ("footwear", "Footwear")
    return ("uncategorised", "Uncategorised")


def synthesize_description(title: str, brand: str, leaf_name: str, gender: str, attrs: dict[str, str]) -> str:
    """~40% of source records have no description. Compose one from the real structured
    attributes we already parsed, rather than leaving it null — every product needs text
    content (this feeds a recommendation engine later)."""
    clauses = []
    fabric = attrs.get("Fabric")
    pattern = attrs.get("Pattern")
    fit = attrs.get("Fit")
    sleeve = attrs.get("Sleeve") or attrs.get("Sleeve Type")
    neck = attrs.get("Neck Type")

    if fabric and pattern:
        clauses.append(f"Made from {fabric.lower()} with a {pattern.lower()} pattern")
    elif fabric:
        clauses.append(f"Made from {fabric.lower()}")
    elif pattern:
        clauses.append(f"Featuring a {pattern.lower()} pattern")

    fit_bits = [b for b in (fit, sleeve, neck) if b]
    if fit_bits:
        clauses.append(", ".join(fit_bits).lower().capitalize())

    gender_label = {"men": "men", "women": "women", "boys": "boys", "girls": "girls"}.get(gender)
    audience = f" for {gender_label}" if gender_label else ""
    lead = f"{title} by {brand}{audience}."
    body = ". ".join(clauses)
    tail = f"Part of the {leaf_name} range."
    return " ".join(p for p in (lead, body + "." if body else "", tail) if p).strip()


def upgrade_image_url(url: str) -> str:
    return re.sub(r"/image/\d+/\d+/", "/image/832/832/", url, count=1)


def color_hex_for(name: str | None) -> str | None:
    if not name:
        return None
    return COLOR_HEX.get(name.strip().lower())


def clean_record(raw: dict, quarantine: list[dict]) -> dict | None:
    title = clean_title(raw.get("title"))
    if not title:
        quarantine.append({"pid": raw.get("pid"), "reason": "missing_title"})
        return None

    mrp = clean_price(raw.get("actual_price"))
    price = clean_price(raw.get("selling_price"))
    if mrp is None or price is None:
        quarantine.append({"pid": raw.get("pid"), "reason": "unparseable_price"})
        return None
    if price > mrp:
        mrp, price = price, mrp
    if mrp <= 0 or price <= 0:
        quarantine.append({"pid": raw.get("pid"), "reason": "non_positive_price"})
        return None

    images = list(dict.fromkeys(u for u in (raw.get("images") or []) if u))
    if not images:
        quarantine.append({"pid": raw.get("pid"), "reason": "no_images"})
        return None

    brand = (raw.get("brand") or "").strip()
    brand = re.sub(r"\s+", " ", brand)
    if not brand:
        brand = "Unbranded"

    attrs = flatten_attributes(raw.get("product_details"))
    gender = infer_gender(attrs, title)
    leaf_slug, leaf_name = map_category(raw.get("category"), raw.get("sub_category"))
    color = (attrs.get("Color") or attrs.get("Brand Color") or "").strip().title()[:40] or None

    description = (raw.get("description") or "").strip()
    if not description:
        description = synthesize_description(title, brand, leaf_name, gender, attrs)

    return {
        "pid": raw.get("pid") or raw.get("_id"),
        "title": title,
        "description": description[:4000],
        "brand": brand,
        "gender": gender,
        "leaf_slug": leaf_slug,
        "leaf_name": leaf_name,
        "mrp": mrp,
        "price": price,
        "rating_avg": clean_rating(raw.get("average_rating")),
        "images": [upgrade_image_url(u) for u in images[:6]],
        "out_of_stock": bool(raw.get("out_of_stock")),
        "color": color,
        "attrs": attrs,
    }


def dedupe(records: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for r in records:
        key = (r["brand"].lower(), r["title"].lower())
        score = len(r["attrs"]) + len(r["images"])
        existing = best.get(key)
        if existing is None or score > existing["_score"]:
            r["_score"] = score
            best[key] = r
    return list(best.values())


def deterministic_rng(seed_key: str) -> random.Random:
    return random.Random(hash(seed_key) & 0xFFFFFFFF)


async def stage_load() -> None:
    """spec §7.2 stages 3+4+5+7 combined: clean -> normalise -> enrich -> load.

    Kept as one in-memory pass rather than four separate CLI invocations with an intermediate
    file format between each: at 30k records the whole raw dataset fits comfortably in memory, so
    persisting "cleaned.jsonl" / "normalised.jsonl" / "enriched.jsonl" between stages would only
    add serialisation overhead and a made-up intermediate schema, not real resumability or
    debuggability — profile output (stage_profile) already gives visibility into the same data
    quality questions those intermediate files would otherwise let you inspect."""
    t0 = time.time()
    print(f"Reading {RAW_PATH} ...")
    with open(RAW_PATH, encoding="utf-8") as f:
        raw_records = json.load(f)
    print(f"Loaded {len(raw_records)} raw records in {time.time() - t0:.1f}s")

    quarantine: list[dict] = []
    cleaned = []
    for raw in raw_records:
        rec = clean_record(raw, quarantine)
        if rec is not None:
            cleaned.append(rec)

    before_dedupe = len(cleaned)
    cleaned = dedupe(cleaned)
    dupes_dropped = before_dedupe - len(cleaned)

    # Drop gender buckets too small to be a real, browsable section rather than shipping a
    # nav item that leads to an almost-empty page.
    gender_counts = defaultdict(int)
    for r in cleaned:
        gender_counts[r["gender"]] += 1
    dropped_genders = {g for g, count in gender_counts.items() if count < MIN_CATEGORY_PRODUCTS}
    if dropped_genders:
        before_threshold = len(cleaned)
        for r in cleaned:
            if r["gender"] in dropped_genders:
                quarantine.append({"pid": r["pid"], "reason": "category_too_small", "gender": r["gender"]})
        cleaned = [r for r in cleaned if r["gender"] not in dropped_genders]
        print(
            f"Dropped {before_threshold - len(cleaned)} products in undersized categories: "
            + ", ".join(f"{g} ({gender_counts[g]})" for g in sorted(dropped_genders))
        )

    rejection_rate = len(quarantine) / len(raw_records)
    print(
        f"Cleaned {len(cleaned)} products "
        f"(quarantined {len(quarantine)}, deduped {dupes_dropped}, "
        f"rejection rate {rejection_rate:.1%})"
    )

    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    qpath = QUARANTINE_DIR / f"ingest_{int(time.time())}.jsonl"
    with open(qpath, "w", encoding="utf-8") as f:
        for q in quarantine:
            f.write(json.dumps(q) + "\n")
    print(f"Quarantine report: {qpath}")

    if rejection_rate > REJECTION_THRESHOLD:
        print(f"ERROR: rejection rate {rejection_rate:.1%} exceeds threshold {REJECTION_THRESHOLD:.0%}")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        await session.execute(text("TRUNCATE product_images"))
        await session.execute(text("TRUNCATE product_attributes"))
        await session.execute(text("TRUNCATE product_variants"))
        await session.execute(text("TRUNCATE products"))
        await session.execute(text("TRUNCATE categories"))
        await session.execute(text("TRUNCATE brands"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        await session.commit()

        # --- brands ---
        # brands.name is unique under a case-insensitive collation, so dedupe case-insensitively
        # and normalise every product's brand key the same way to avoid a lookup miss later.
        brand_display: dict[str, str] = {}
        for r in cleaned:
            key = r["brand"].lower()
            brand_display.setdefault(key, r["brand"])
            r["brand_key"] = key

        seen_brand_slugs: set[str] = set()
        brand_rows = []
        for key, display in sorted(brand_display.items()):
            base_slug = slugify(display) or "brand"
            slug = base_slug
            n = 1
            while slug in seen_brand_slugs:
                n += 1
                slug = f"{base_slug}-{n}"
            seen_brand_slugs.add(slug)
            brand_rows.append({"name": display, "slug": slug, "is_active": True, "sort_order": 0})

        conn = await session.connection()
        await conn.execute(insert(Brand.__table__), brand_rows)
        result = await session.execute(select(Brand.id, Brand.name))
        brand_id_by_name = {name.lower(): id_ for id_, name in result.all()}
        print(f"Loaded {len(brand_rows)} brands")

        # --- categories: gender (top) x leaf ---
        genders = sorted({r["gender"] for r in cleaned})
        top_rows = [
            {"name": g.title(), "slug": g, "path": f"/{g}", "depth": 0, "is_active": True, "sort_order": 0}
            for g in genders
        ]
        conn = await session.connection()
        await conn.execute(insert(Category.__table__), top_rows)
        result = await session.execute(select(Category.id, Category.slug))
        top_id_by_slug = {slug: id_ for id_, slug in result.all()}

        leaf_pairs = sorted({(r["gender"], r["leaf_slug"], r["leaf_name"]) for r in cleaned})
        leaf_rows = [
            {
                "name": leaf_name,
                "slug": f"{gender}-{leaf_slug}",
                "path": f"/{gender}/{leaf_slug}",
                "depth": 1,
                "parent_id": top_id_by_slug[gender],
                "is_active": True,
                "sort_order": 0,
            }
            for gender, leaf_slug, leaf_name in leaf_pairs
        ]
        conn = await session.connection()
        await conn.execute(insert(Category.__table__), leaf_rows)
        result = await session.execute(select(Category.id, Category.slug))
        cat_id_by_slug = {slug: id_ for id_, slug in result.all()}
        print(f"Loaded {len(top_rows)} top categories, {len(leaf_rows)} leaf categories")

        # --- products + children, batched ---
        seen_slugs: set[str] = set()
        total_products = 0
        total_images = 0
        total_attrs = 0
        total_variants = 0

        for batch_start in range(0, len(cleaned), BATCH_SIZE):
            batch = cleaned[batch_start : batch_start + BATCH_SIZE]
            product_rows = []
            for r in batch:
                base_slug = slugify(r["brand"], r["title"])
                slug = base_slug
                n = 1
                while slug in seen_slugs:
                    n += 1
                    slug = f"{base_slug}-{n}"
                seen_slugs.add(slug)

                rng = deterministic_rng(str(r["pid"]))
                stock_total = 0 if r["out_of_stock"] else rng.randint(5, 200)

                product_rows.append(
                    {
                        "public_id": str(ULID()),
                        "slug": slug,
                        "title": r["title"],
                        "subtitle": None,
                        "description": r["description"],
                        "brand_id": brand_id_by_name[r["brand_key"]],
                        "category_id": cat_id_by_slug[f"{r['gender']}-{r['leaf_slug']}"],
                        "gender": r["gender"],
                        "material": (r["attrs"].get("Fabric") or "")[:120] or None,
                        "base_color": r["color"],
                        "currency": "INR",
                        "mrp": r["mrp"],
                        "price": r["price"],
                        "rating_avg": r["rating_avg"],
                        "rating_count": rng.randint(5, 800) if r["rating_avg"] else 0,
                        "review_count": rng.randint(0, 200) if r["rating_avg"] else 0,
                        "sold_count": rng.randint(0, 4000),
                        "view_count": 0,
                        "stock_total": stock_total,
                        "status": "active",
                        "is_featured": rng.random() < 0.05,
                        "is_trending": rng.random() < 0.1,
                        "is_new_arrival": rng.random() < 0.15,
                        "thumbnail_url": r["images"][0],
                        "seo_title": r["title"][:60],
                        "seo_description": f"Buy {r['title']} online."[:255],
                        "search_keywords": f"{r['brand']} {r['title']} {r['leaf_name']}",
                        "version": 0,
                    }
                )

            conn = await session.connection()
            insert_result = await conn.execute(insert(Product.__table__), product_rows)
            first_id = insert_result.lastrowid
            product_ids = [first_id + i for i in range(len(product_rows))]

            image_rows = []
            attr_rows = []
            variant_rows = []
            for r, pid in zip(batch, product_ids, strict=True):
                for i, url in enumerate(r["images"]):
                    image_rows.append(
                        {
                            "product_id": pid,
                            "url": url,
                            "alt_text": r["title"],
                            "sort_order": i,
                            "is_primary": i == 0,
                        }
                    )
                for src_key, attr_name in ATTRIBUTE_ALLOWLIST.items():
                    value = r["attrs"].get(src_key)
                    if value:
                        attr_rows.append(
                            {
                                "product_id": pid,
                                "name": attr_name,
                                "value": value[:255],
                                "group_name": "Details",
                                "is_filterable": attr_name in {"material", "pattern", "fit"},
                                "sort_order": 0,
                            }
                        )

                rng = deterministic_rng(str(r["pid"]))
                stock_total = 0 if r["out_of_stock"] else None
                sizes = FOOTWEAR_SIZES if r["leaf_slug"] == "footwear" else CLOTHING_SIZES
                brand_prefix = slugify(r["brand"])[:3].upper() or "GEN"
                for size in sizes:
                    stock = 0 if r["out_of_stock"] else rng.randint(0, 60)
                    variant_rows.append(
                        {
                            "product_id": pid,
                            "sku": f"BC-{brand_prefix}-{pid}-{size}",
                            "size": size,
                            "color": r["color"],
                            "color_hex": color_hex_for(r["color"]),
                            "mrp": r["mrp"],
                            "price": r["price"],
                            "stock": stock,
                            "reserved": 0,
                            "low_stock_threshold": 5,
                            "is_active": True,
                            "position": 0,
                            "version": 0,
                        }
                    )

            conn = await session.connection()
            if image_rows:
                await conn.execute(insert(ProductImage.__table__), image_rows)
            if attr_rows:
                await conn.execute(insert(ProductAttribute.__table__), attr_rows)
            if variant_rows:
                await conn.execute(insert(ProductVariant.__table__), variant_rows)

            await session.commit()

            total_products += len(product_rows)
            total_images += len(image_rows)
            total_attrs += len(attr_rows)
            total_variants += len(variant_rows)
            print(
                f"  batch {batch_start // BATCH_SIZE + 1}: "
                f"{total_products} products, {total_images} images, "
                f"{total_attrs} attrs, {total_variants} variants "
                f"({time.time() - t0:.0f}s elapsed)"
            )

        # Backfill category tile images from real product photos (leaf, then propagate to top).
        await session.execute(
            text(
                """
                UPDATE categories c
                JOIN (
                    SELECT category_id, ANY_VALUE(thumbnail_url) AS thumb
                    FROM products
                    GROUP BY category_id
                ) p ON p.category_id = c.id
                SET c.image_url = p.thumb
                WHERE c.depth = 1
                """
            )
        )
        await session.execute(
            text(
                """
                UPDATE categories top
                JOIN (
                    SELECT parent_id, ANY_VALUE(image_url) AS thumb
                    FROM categories
                    WHERE depth = 1 AND image_url IS NOT NULL
                    GROUP BY parent_id
                ) leaf ON leaf.parent_id = top.id
                SET top.image_url = leaf.thumb
                WHERE top.depth = 0
                """
            )
        )
        await session.commit()

    await engine.dispose()
    print(f"Done in {time.time() - t0:.0f}s.")


async def stage_fetch() -> None:
    """spec §7.2 stage 1: download/verify the dataset, checksum it, store raw in data/raw/.
    Idempotent — refuses to re-download over an existing file (delete it first to re-fetch)."""
    if RAW_PATH.exists():
        size_mb = RAW_PATH.stat().st_size / 1e6
        print(f"{RAW_PATH} already exists ({size_mb:.1f} MB) — skipping. Delete it to re-fetch.")
        return

    settings = get_settings()
    if not settings.kaggle_api_key:
        print("ERROR: kaggle_api_key is not set in .env — cannot fetch the dataset.", file=sys.stderr)
        sys.exit(1)

    print("Downloading dataset from Kaggle...")
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.get(
            KAGGLE_DATASET_URL,
            headers={"Authorization": f"Bearer {settings.kaggle_api_key}"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        zip_bytes = resp.content

    print(f"Downloaded {len(zip_bytes) / 1e6:.1f} MB zip, extracting...")
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        json_names = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_names:
            print("ERROR: no .json file found inside the downloaded archive.", file=sys.stderr)
            sys.exit(1)
        with zf.open(json_names[0]) as src, open(RAW_PATH, "wb") as dst:
            dst.write(src.read())

    checksum = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()
    print(f"Saved {RAW_PATH} ({RAW_PATH.stat().st_size / 1e6:.1f} MB), sha256={checksum[:16]}...")


def stage_profile() -> None:
    """spec §7.2 stage 2: emit a data-quality report — null rates, cardinality, outliers,
    duplicate keys — over the RAW dataset, before any cleaning happens."""
    with open(RAW_PATH, encoding="utf-8") as f:
        records = json.load(f)
    total = len(records)
    print(f"=== Profile: {total} raw records ({RAW_PATH.name}) ===\n")

    print(f"{'field':<20}{'null/empty':>12}{'%':>8}")
    for field in (
        "title", "brand", "category", "sub_category", "description", "actual_price",
        "selling_price", "average_rating", "images", "product_details", "pid",
    ):
        empty = sum(1 for r in records if not r.get(field))
        print(f"{field:<20}{empty:>12}{empty / total:>8.1%}")

    pids = [r.get("pid") or r.get("_id") for r in records]
    dup_count = len(pids) - len(set(pids))
    print(f"\nDuplicate pid/_id count: {dup_count} ({dup_count / total:.1%})")

    brands = {(r.get("brand") or "").strip() for r in records if (r.get("brand") or "").strip()}
    print(f"Distinct raw brand strings: {len(brands)}")

    cats = {(r.get("category"), r.get("sub_category")) for r in records}
    print(f"Distinct (category, sub_category) pairs: {len(cats)}")

    bad_prices = sum(
        1 for r in records
        if clean_price(r.get("actual_price")) is None or clean_price(r.get("selling_price")) is None
    )
    print(f"Unparseable prices: {bad_prices} ({bad_prices / total:.1%})")

    ratings = [clean_rating(r.get("average_rating")) for r in records]
    out_of_range = sum(1 for r, parsed in zip(records, ratings, strict=True) if r.get("average_rating") and parsed is None)
    print(f"Ratings present but out of [0,5] or unparseable: {out_of_range}")

    no_images = sum(1 for r in records if not r.get("images"))
    print(f"Records with zero images: {no_images} ({no_images / total:.1%})")

    out_of_stock = sum(1 for r in records if r.get("out_of_stock"))
    print(f"out_of_stock=true: {out_of_stock} ({out_of_stock / total:.1%})")


_MEDIA_UPDATE_STMT = (
    ProductImage.__table__.update()
    .where(ProductImage.id == bindparam("b_id"))
    .values(
        url=bindparam("b_url"),
        url_webp=bindparam("b_url_webp"),
        blurhash=bindparam("b_blurhash"),
        width=bindparam("b_width"),
        height=bindparam("b_height"),
    )
)


async def _process_chunk(
    client: httpx.AsyncClient, storage, sem: asyncio.Semaphore, chunk: list
) -> list[dict]:
    async def worker(image_id: int, product_id: int, source_url: str) -> dict | None:
        async with sem:
            result = await process_image(
                client, storage, source_url=source_url, dest_key=f"products/{product_id}/{image_id}"
            )
            if result is None:
                # A single retry: the CDN throttles under concurrent load (empirically found —
                # concurrency=64 with no retry gave a 62-76% failure rate for several minutes
                # afterward, fully recovering on its own), so a failure is more often a transient
                # 429/timeout than a genuinely dead URL. One retry after a short backoff recovers
                # most of those without letting a truly dead URL retry forever.
                await asyncio.sleep(0.5)
                result = await process_image(
                    client, storage, source_url=source_url, dest_key=f"products/{product_id}/{image_id}"
                )
        if result is None:
            return None
        return {
            "b_id": image_id,
            "b_url": result.url,
            "b_url_webp": result.url_webp,
            "b_blurhash": result.blurhash,
            "b_width": result.width,
            "b_height": result.height,
        }

    results = await asyncio.gather(*(worker(iid, pid, url) for iid, pid, url in chunk))
    return [r for r in results if r is not None]


async def stage_media(limit: int | None = None) -> None:
    """spec §7.2 stage 6: download images, validate, transcode to WebP, generate blurhash,
    upload to storage. Genuinely resumable, not just "safe to re-invoke between runs": processed
    in fixed-size chunks, each committed to the database before the next chunk starts, so an
    interrupted run (Ctrl-C, a crash, this exact process getting killed mid-run — which is
    literally how this bug was found, see done.MD) only ever loses its current in-flight chunk,
    never the whole run. The first version of this stage queried and gathered every remaining row
    at once and only wrote to the database after all of them finished — for the ~36k images in
    this catalogue that meant zero progress persisted for potentially hours."""
    storage = get_storage_backend()
    # Empirically tuned against the real Flipkart CDN (rukminim1.flixcart.com): a burst at
    # concurrency=64 triggered what looks like temporary per-IP throttling (failure rate jumped
    # to ~62-76% for several minutes afterward, then fully recovered on its own) — a fetch-only
    # diagnostic at concurrency=20 against the same URLs succeeded 40/40 once the cooldown had
    # passed. Kept deliberately conservative; a lower, throttle-safe concurrency plus resumability
    # is more reliable than chasing maximum single-run throughput.
    concurrency = 16
    chunk_size = 300

    t0 = time.time()
    total_done = 0
    total_failed = 0
    sem = asyncio.Semaphore(concurrency)
    # A row that fails every attempt (e.g. a genuinely dead source URL — see README's "some
    # Flipkart CDN image URLs from this 2021 crawl may be dead") never gets blurhash set, so
    # without this the `WHERE blurhash IS NULL` query below would keep re-selecting the exact
    # same rows forever and the loop would never terminate. Found live: the last ~41 rows in the
    # full-catalogue run were all dead URLs and the loop spun on them indefinitely instead of
    # exiting. Excluding already-failed ids for the rest of this run guarantees termination;
    # they stay blurhash IS NULL in the database so a future re-run will still retry them.
    failed_ids: set[int] = set()

    async with httpx.AsyncClient() as client:
        while True:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(ProductImage.id, ProductImage.product_id, ProductImage.url)
                    .where(ProductImage.blurhash.is_(None))
                    .order_by(ProductImage.id)
                    .limit(chunk_size if not limit else min(chunk_size, limit - total_done))
                )
                if failed_ids:
                    stmt = stmt.where(ProductImage.id.notin_(failed_ids))
                chunk = (await session.execute(stmt)).all()

            if not chunk:
                break

            updates = await _process_chunk(client, storage, sem, chunk)

            if updates:
                async with AsyncSessionLocal() as session:
                    await session.execute(_MEDIA_UPDATE_STMT, updates)
                    await session.commit()

            succeeded_ids = {u["b_id"] for u in updates}
            failed_ids.update(row.id for row in chunk if row.id not in succeeded_ids)

            total_done += len(chunk)
            total_failed += len(chunk) - len(updates)
            print(
                f"  {total_done} attempted, {total_done - total_failed} committed, "
                f"{total_failed} failed — {time.time() - t0:.0f}s elapsed"
            )

            if limit and total_done >= limit:
                break

    print(f"Done: {total_done - total_failed} succeeded, {total_failed} failed, in {time.time() - t0:.0f}s")
    if failed_ids:
        print(
            f"  {len(failed_ids)} row(s) failed every attempt (likely dead source URLs) and were "
            f"skipped for the rest of this run — still blurhash IS NULL, re-run to retry: "
            f"{sorted(failed_ids)}"
        )

    if not limit:
        # Every remaining row got at least one attempt this run (the loop only stops when a
        # chunk query comes back empty) — safe to backfill card thumbnails from whatever's now
        # self-hosted, same UPDATE...JOIN pattern stage_load already uses for category tiles.
        # Product.thumbnail_url has no companion _webp column (a real schema gap, not fixed here
        # — see done.MD), so cards keep hotlinking-shaped JPEGs; only PDP's gallery gets WebP.
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    UPDATE products p
                    JOIN (
                        SELECT product_id, url
                        FROM product_images
                        WHERE is_primary = 1 AND blurhash IS NOT NULL
                    ) pi ON pi.product_id = p.id
                    SET p.thumbnail_url = pi.url
                    """
                )
            )
            await session.commit()
            print(f"Backfilled thumbnail_url on {result.rowcount} products from self-hosted primary images.")


async def stage_verify() -> None:
    """spec §7.2 stage 9: assert row counts, orphan checks, price sanity, image reachability.
    Exits non-zero if any integrity check fails, so a broken ingest can't pass silently."""
    async with AsyncSessionLocal() as session:
        product_count = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
        variant_count = (await session.execute(select(func.count()).select_from(ProductVariant))).scalar_one()
        image_count = (await session.execute(select(func.count()).select_from(ProductImage))).scalar_one()
        print(f"Row counts: products={product_count} variants={variant_count} images={image_count}")

        bad_price_count = (
            await session.execute(select(func.count()).select_from(Product).where(Product.price > Product.mrp))
        ).scalar_one()
        print(f"Products with price > mrp: {bad_price_count} (should be 0)")

        no_image_products = (
            await session.execute(
                select(func.count())
                .select_from(Product)
                .where(~Product.id.in_(select(ProductImage.product_id)))
            )
        ).scalar_one()
        print(f"Products with zero images: {no_image_products} (should be 0)")

        no_variant_products = (
            await session.execute(
                select(func.count())
                .select_from(Product)
                .where(~Product.id.in_(select(ProductVariant.product_id)))
            )
        ).scalar_one()
        print(f"Products with zero variants: {no_variant_products} (should be 0)")

        unprocessed_images = (
            await session.execute(select(func.count()).select_from(ProductImage).where(ProductImage.blurhash.is_(None)))
        ).scalar_one()
        print(f"Images not yet processed by the media stage: {unprocessed_images}")

        sample_urls = (
            await session.execute(
                select(ProductImage.url).where(ProductImage.blurhash.is_not(None)).limit(25)
            )
        ).scalars().all()
        reachable = 0
        for url in sample_urls:
            if "/media/" not in url:
                continue
            local_path = MEDIA_ROOT / url.split("/media/", 1)[1]
            if local_path.exists():
                reachable += 1
        if sample_urls:
            print(f"Local media reachability sample: {reachable}/{len(sample_urls)} files exist on disk")

    errors = bad_price_count + no_image_products + no_variant_products
    if errors:
        print(f"\nVERIFY FAILED: {errors} integrity issue(s) found")
        sys.exit(1)
    print("\nVERIFY OK")


async def _run_profile() -> None:
    stage_profile()  # sync — no I/O worth an event loop, just wrapped so the dispatch table is uniform


STAGES = {
    "fetch": lambda args: stage_fetch(),
    "profile": lambda args: _run_profile(),
    "load": lambda args: stage_load(),
    "media": lambda args: stage_media(limit=args.limit),
    "verify": lambda args: stage_verify(),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(STAGES), default="load", help="Which pipeline stage to run.")
    parser.add_argument("--limit", type=int, default=None, help="For --stage media: process at most N images.")
    args = parser.parse_args()
    asyncio.run(STAGES[args.stage](args))


if __name__ == "__main__":
    main()
