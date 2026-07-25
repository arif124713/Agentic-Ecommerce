"""Seed a couple of demo coupons so checkout's coupon-apply path is actually testable. Admin
coupon CRUD (spec §10.8 admin endpoints) is Phase 4 territory and hasn't been built — this script
stands in for it. Idempotent — safe to re-run. Run: python scripts/seed_coupons.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.commerce import Coupon  # noqa: E402

COUPONS = [
    dict(
        code="WELCOME10",
        description="10% off your first order",
        discount_type="percent",
        discount_value=Decimal("10"),
        max_discount_amount=Decimal("300"),
        min_order_amount=Decimal("500"),
        usage_limit_total=None,
        usage_limit_per_user=1,
    ),
    dict(
        code="FLAT100",
        description="Flat 100 off orders over 1000",
        discount_type="fixed",
        discount_value=Decimal("100"),
        max_discount_amount=None,
        min_order_amount=Decimal("1000"),
        usage_limit_total=None,
        usage_limit_per_user=None,
    ),
    dict(
        code="FREESHIP",
        description="Free shipping, no minimum",
        discount_type="free_shipping",
        discount_value=Decimal("0"),
        max_discount_amount=None,
        min_order_amount=None,
        usage_limit_total=None,
        usage_limit_per_user=None,
    ),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for data in COUPONS:
            existing = (
                await session.execute(select(Coupon).where(Coupon.code == data["code"]))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Coupon(**data, stackable=False, is_active=True))
        await session.commit()
        print(f"Seeded {len(COUPONS)} coupons.")


if __name__ == "__main__":
    asyncio.run(seed())
