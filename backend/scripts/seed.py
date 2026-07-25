"""Seed the catalogue with a representative sample so the storefront has real data to render.

This stands in for the full 9-stage Flipkart ingestion pipeline (spec §7), which needs
Kaggle credentials and a multi-GB download. Run: python scripts/seed.py
"""

import asyncio
import random
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulid import ULID  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.models.catalog import Brand, Category, Product, ProductAttribute, ProductImage, ProductVariant  # noqa: E402

random.seed(42)

BRANDS = ["Nike", "Adidas", "Puma", "Levi's", "H&M", "Zara", "Uniqlo", "Reebok", "Fabindia", "Allen Solly"]

CATEGORIES = [
    ("Men", "men", [
        ("T-Shirts", "men-tshirts"), ("Shirts", "men-shirts"), ("Jeans", "men-jeans"),
        ("Jackets", "men-jackets"), ("Footwear", "men-footwear"),
    ]),
    ("Women", "women", [
        ("Dresses", "women-dresses"), ("Tops", "women-tops"), ("Jeans", "women-jeans"),
        ("Kurtis", "women-kurtis"), ("Footwear", "women-footwear"),
    ]),
    ("Kids", "kids", [
        ("Boys Clothing", "kids-boys"), ("Girls Clothing", "kids-girls"),
    ]),
]

PRODUCT_NOUNS = {
    "T-Shirts": ["Oversized Tee", "Crew Neck T-Shirt", "Graphic Tee", "Polo T-Shirt"],
    "Shirts": ["Casual Shirt", "Formal Shirt", "Denim Shirt", "Linen Shirt"],
    "Jeans": ["Slim Fit Jeans", "Straight Fit Jeans", "Relaxed Jeans", "Skinny Jeans"],
    "Jackets": ["Bomber Jacket", "Denim Jacket", "Puffer Jacket", "Windcheater"],
    "Footwear": ["Running Shoes", "Sneakers", "Sandals", "Loafers"],
    "Dresses": ["Wrap Dress", "Maxi Dress", "A-Line Dress", "Bodycon Dress"],
    "Tops": ["Crop Top", "Tank Top", "Blouse", "Peplum Top"],
    "Kurtis": ["Straight Kurti", "A-Line Kurti", "Anarkali Kurti"],
    "Boys Clothing": ["Boys T-Shirt", "Boys Shorts", "Boys Jeans"],
    "Girls Clothing": ["Girls Frock", "Girls Leggings", "Girls Top"],
}

COLORS = [("Black", "#000000"), ("White", "#FFFFFF"), ("Navy", "#1B2A4A"), ("Grey", "#808080"), ("Olive", "#556B2F")]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]


def slugify(*parts: str) -> str:
    return "-".join(p.lower().replace(" ", "-").replace("'", "") for p in parts)


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await session.get(Brand, 1)
        if existing is not None:
            print("Already seeded (brand id=1 exists). Skipping.")
            return

        brands = []
        for name in BRANDS:
            brand = Brand(name=name, slug=slugify(name), is_active=True, sort_order=0)
            session.add(brand)
            brands.append(brand)
        await session.flush()

        product_count = 0
        for top_name, top_slug, subcats in CATEGORIES:
            top = Category(name=top_name, slug=top_slug, path=f"/{top_slug}", depth=0, is_active=True)
            session.add(top)
            await session.flush()

            for sub_name, sub_slug in subcats:
                sub = Category(
                    name=sub_name,
                    slug=sub_slug,
                    path=f"/{top_slug}/{sub_slug}",
                    depth=1,
                    parent_id=top.id,
                    is_active=True,
                )
                session.add(sub)
                await session.flush()

                nouns = PRODUCT_NOUNS.get(sub_name, [f"{sub_name} Item"])
                for i in range(14):
                    brand = random.choice(brands)
                    noun = random.choice(nouns)
                    product_count += 1
                    title = f"{brand.name} {noun} {i + 1}"
                    mrp = Decimal(random.randrange(799, 5999, 100))
                    discount_pct = random.choice([0, 10, 20, 30, 40])
                    price = (mrp * (100 - discount_pct) / 100).quantize(Decimal("1"))

                    product = Product(
                        public_id=str(ULID()),
                        slug=slugify(brand.name, noun, str(product_count)),
                        title=title,
                        subtitle=f"{sub_name} by {brand.name}",
                        description=(
                            f"The {title} is crafted for everyday comfort with a modern silhouette, "
                            f"breathable fabric, and durable stitching. Part of the {top_name} {sub_name} range."
                        ),
                        brand_id=brand.id,
                        category_id=sub.id,
                        gender="men" if top_slug == "men" else ("women" if top_slug == "women" else "kids"),
                        material=random.choice(["Cotton", "Polyester", "Denim", "Linen", "Blend"]),
                        base_color=random.choice(COLORS)[0],
                        currency="BDT",
                        mrp=mrp,
                        price=price,
                        rating_avg=Decimal(str(round(random.uniform(3.2, 4.9), 1))),
                        rating_count=random.randint(3, 480),
                        review_count=random.randint(1, 200),
                        sold_count=random.randint(0, 5000),
                        stock_total=0,
                        status="active",
                        is_featured=random.random() < 0.12,
                        is_trending=random.random() < 0.15,
                        is_new_arrival=random.random() < 0.2,
                        thumbnail_url=f"https://picsum.photos/seed/{slugify(brand.name, noun, str(i+1))}/800/1000",
                        seo_title=title[:60],
                        seo_description=f"Shop {title} online.",
                        search_keywords=f"{brand.name} {noun} {sub_name} {top_name}",
                    )
                    session.add(product)
                    await session.flush()

                    session.add(
                        ProductImage(
                            product_id=product.id,
                            url=str(product.thumbnail_url),
                            alt_text=title,
                            sort_order=0,
                            is_primary=True,
                        )
                    )
                    session.add(
                        ProductAttribute(
                            product_id=product.id,
                            name="material",
                            value=product.material,
                            group_name="Fabric & Care",
                            is_filterable=True,
                        )
                    )

                    total_stock = 0
                    chosen_colors = random.sample(COLORS, k=min(2, len(COLORS)))
                    chosen_sizes = random.sample(SIZES, k=4)
                    for color_name, color_hex in chosen_colors:
                        for size in chosen_sizes:
                            stock = random.randint(0, 60)
                            total_stock += stock
                            session.add(
                                ProductVariant(
                                    product_id=product.id,
                                    sku=f"BC-{brand.slug[:3].upper()}-{product.id}-{size}-{color_name[:3].upper()}",
                                    size=size,
                                    color=color_name,
                                    color_hex=color_hex,
                                    mrp=mrp,
                                    price=price,
                                    stock=stock,
                                    reserved=0,
                                    is_active=True,
                                )
                            )
                    product.stock_total = total_stock

        await session.commit()
        print(f"Seeded {len(brands)} brands and {product_count} products.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
