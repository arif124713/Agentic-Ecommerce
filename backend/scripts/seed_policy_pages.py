"""Seed/update the CmsPage rows support-mcp's `search_policy_kb` tool searches (chat_spec.md
§4.3). Reuses the EXISTING `cms_pages` table (`app/models/cms.py`) rather than a parallel content
store — it already has exactly the shape this needs (slug, title, body, published/draft, rendered
publicly at /pages/{slug}). `returns-policy` already existed as a 50-char draft stub; this replaces
it with real content and publishes it, and adds four more policy pages alongside it.

Figures below (shipping fee, free-shipping threshold, COD surcharge, delivery window) are pulled
from the SAME Settings defaults the checkout flow itself uses (app/core/config.py) — not invented
separately, so this content can't silently drift from what a customer actually gets charged.
Bodies use `## Heading` markdown sections since `search_policy_kb` splits/cites by heading.

Run: python scripts/seed_policy_pages.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.cms import CmsPage  # noqa: E402

settings = get_settings()

PAGES = [
    {
        "slug": "shipping-policy",
        "title": "Shipping & Delivery",
        "body": f"""## Delivery Timeline

Orders are delivered in {settings.delivery_min_days}-{settings.delivery_max_days} business days from the day the order is placed, depending on your location within Bangladesh. You'll see an estimated delivery window on your order confirmation.

## Shipping Fees

Standard shipping is ৳{settings.shipping_flat_fee} per order. Orders over ৳{settings.free_shipping_threshold} ship free automatically — no code needed, the discount applies at checkout.

## Order Tracking

Once your order ships, you'll get tracking updates in the Support tab (just ask "where's my order") and by email. Tracking shows carrier, current status, and estimated delivery date.
""",
        "status": "published",
    },
    {
        "slug": "returns-policy",
        "title": "Returns Policy",
        "body": f"""## Return Window

You can request a return within {settings.return_window_days} days of delivery. The window starts the day the order is marked delivered, not the day you placed it.

## Condition Requirements

Items must be unworn, unwashed, and with original tags attached to qualify for return. Innerwear, swimwear, and customized items are final sale and can't be returned for hygiene/customization reasons.

## How to Start a Return

Ask in the Support tab which item you'd like to return and why — we'll confirm it's eligible, walk you through the reason, and create the return request. Once approved, we'll share pickup or drop-off instructions.
""",
        "status": "published",
    },
    {
        "slug": "refunds-policy",
        "title": "Refunds & Payment Issues",
        "body": """## Refund Timeline

Once a returned item is received and inspected, refunds are issued within 5-7 business days. The money lands back on your original payment method — we can't redirect a refund to a different card or account.

## Refund Methods

Card and mobile-banking payments are refunded to the same method automatically. Cash-on-delivery orders are refunded via bank transfer or mobile wallet — we'll ask for those details once your return is approved.
""",
        "status": "published",
    },
    {
        "slug": "sizing-guide",
        "title": "Sizing & Fit",
        "body": """## How to Read Our Size Chart

Each product page has a size chart tab with body measurements (chest, waist, hip, length) for every size the item comes in — measurements are of the garment, not "true to body," so check the chart rather than assuming your usual size across brands.

## Common Fit Issues

Between sizes? We generally recommend sizing up for a relaxed fit and down for a fitted look — the product description usually notes if an item runs small or large. If a size turns out wrong, it's covered under the normal return window.
""",
        "status": "published",
    },
    {
        "slug": "payment-methods",
        "title": "Payment Methods",
        "body": f"""## Accepted Payment Methods

We accept major debit/credit cards and mobile banking (bKash, Nagad, Rocket) at checkout, along with cash on delivery.

## Cash on Delivery

Cash on delivery orders carry a ৳{settings.cod_surcharge} surcharge to cover collection costs. Have the exact amount ready for the delivery agent where possible.

## Payment Security

Card and mobile-banking payments are processed through our payment provider — we never store your full card number or banking PIN on our own servers.
""",
        "status": "published",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        for page in PAGES:
            existing = (
                await session.execute(select(CmsPage).where(CmsPage.slug == page["slug"]))
            ).scalar_one_or_none()
            if existing:
                existing.title = page["title"]
                existing.body = page["body"]
                existing.status = page["status"]
                print(f"Updated {page['slug']}")
            else:
                session.add(CmsPage(**page))
                print(f"Inserted {page['slug']}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
