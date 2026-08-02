"""Full (re)index of every active, non-deleted product into Algolia (spec §14 — see
core/search_backend.py's own docstring for the record shape and why Algolia rather than literal
Elasticsearch). Configures the index's settings/synonyms first (idempotent, safe to re-run), then
pushes every product as one batched write rather than one Algolia call per product.

Windows-only note: aiomysql's SSL connection to a managed host (Aiven) hits a real asyncio bug
under the default ProactorEventLoop (WinError 87) — see done.MD. Only relevant when running this
script *locally* against a managed MySQL instance; Vercel's Linux runtime never hits it, and this
script is operator tooling that only ever runs from a developer machine, same as every other script
in this directory.

Run: python scripts/reindex_algolia.py
"""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.search_backend import AlgoliaSearchBackend, product_to_record  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.catalog import Product  # noqa: E402


async def main() -> None:
    backend = AlgoliaSearchBackend()  # raises with a clear message if ALGOLIA_* isn't configured
    try:
        print("Configuring index settings + synonyms...", flush=True)
        await backend.configure_index()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Product)
                .where(Product.status == "active", Product.deleted_at.is_(None))
                .options(
                    selectinload(Product.brand),
                    selectinload(Product.category),
                    selectinload(Product.variants),
                )
            )
            products = list((await session.execute(stmt)).scalars().all())

        print(f"Indexing {len(products)} active products...", flush=True)
        # save_objects (inside index_products) chunks into batches of 1000 itself — no manual loop.
        await backend.index_products(products)

        print(f"Done. {len(products)} products indexed.")
        if products:
            sample = product_to_record(products[0])
            print(f"Sample record: {sample['slug']} (objectID {sample['objectID']})")
    finally:
        await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
