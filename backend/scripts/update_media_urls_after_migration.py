"""Run once, after scripts/migrate_media_to_storage.py has fully finished: rewrites every stored
media URL from the local dev prefix (http://<backend_base_url>/media/) to the new remote storage
backend's public base URL.

Safe as a single bulk string-prefix replace rather than a per-row remap: the migration script
uploads every file under its own local `relative_path` unchanged, so the only thing that differs
between the old and new URL is the domain in front of it.

Run: python scripts/update_media_urls_after_migration.py <new_public_base_url>
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, update  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.catalog import Product, ProductImage  # noqa: E402


async def main(new_base_url: str) -> None:
    old_prefix = f"{get_settings().backend_base_url}/media/"
    new_prefix = new_base_url.rstrip("/") + "/"

    async with AsyncSessionLocal() as session:
        before = (
            await session.execute(
                select(func.count()).select_from(ProductImage).where(ProductImage.url.like(f"{old_prefix}%"))
            )
        ).scalar_one()
        print(f"{before} product_images.url rows currently point at the local prefix.")

        await session.execute(
            update(ProductImage)
            .where(ProductImage.url.like(f"{old_prefix}%"))
            .values(url=func.replace(ProductImage.url, old_prefix, new_prefix))
        )
        await session.execute(
            update(ProductImage)
            .where(ProductImage.url_webp.like(f"{old_prefix}%"))
            .values(url_webp=func.replace(ProductImage.url_webp, old_prefix, new_prefix))
        )
        await session.execute(
            update(Product)
            .where(Product.thumbnail_url.like(f"{old_prefix}%"))
            .values(thumbnail_url=func.replace(Product.thumbnail_url, old_prefix, new_prefix))
        )
        await session.commit()

        remaining = (
            await session.execute(
                select(func.count()).select_from(ProductImage).where(ProductImage.url.like(f"{old_prefix}%"))
            )
        ).scalar_one()
        print(f"Done. {remaining} product_images.url rows still on the old prefix (should be 0).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/update_media_urls_after_migration.py <new_blob_base_url>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
