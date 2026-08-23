"""Recomputes the three MySQL summary tables analytics-mcp reads (chat_implementation_plan.md §6 —
the plain-table replacement for spec §10.1's Postgres materialized views). Connects with the
PRIMARY db role (analytics_ro is intentionally SELECT-only and can't write these).

In production this is what a Vercel Cron endpoint calls every 15 minutes (spec's refresh cadence);
here it's a standalone script since the cron endpoint itself is M8 (harden & ship) work — this is
the actual computation, callable both ways.

Uses plain Python aggregation over fetched rows rather than one large SQL query per table. That's
the right tradeoff at BlackCart's current order volume (order history spans days, not years) and
keeps the logic easy to verify by hand; if order volume grows enough for this to matter, the loop
below should become real SQL GROUP BY aggregation instead of a rewrite of what it computes.

Run: python scripts/refresh_analytics_summaries.py
"""

import asyncio
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.core.timeutil import utcnow  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.analytics import CategoryPerformanceSummary, DailySalesSummary, ProductVelocitySummary  # noqa: E402
from app.models.catalog import Product, ProductVariant  # noqa: E402
from app.models.commerce import Order, OrderItem, Refund, Return  # noqa: E402

_PAID_STATUSES = {"paid", "partially_refunded", "refunded"}
_WINDOW_DAYS = 90  # how far back to (re)build daily_sales_summary / category_performance_summary


async def _refresh_daily_sales(session) -> int:
    cutoff = utcnow() - timedelta(days=_WINDOW_DAYS)
    orders = list(
        (
            await session.execute(
                select(Order).where(Order.created_at >= cutoff).order_by(Order.created_at)
            )
        )
        .scalars()
        .all()
    )
    order_ids = [o.id for o in orders]
    items_by_order: dict[int, int] = defaultdict(int)
    if order_ids:
        for order_id, qty in await session.execute(
            select(OrderItem.order_id, OrderItem.quantity).where(OrderItem.order_id.in_(order_ids))
        ):
            items_by_order[order_id] += qty

    refunds = list(
        (await session.execute(select(Refund).where(Refund.created_at >= cutoff))).scalars().all()
    )
    refunds_by_order: dict[int, list[Refund]] = defaultdict(list)
    for r in refunds:
        refunds_by_order[r.order_id].append(r)

    # first-ever-order date per user, among ALL of their orders (not just the trailing window) —
    # needed to tell new vs. returning customers correctly even right at the window's edge.
    all_user_first_order: dict[int, datetime] = {}
    for user_id, created_at in await session.execute(select(Order.user_id, Order.created_at)):
        if user_id is None:
            continue
        if user_id not in all_user_first_order or created_at < all_user_first_order[user_id]:
            all_user_first_order[user_id] = created_at

    by_date: dict[date, list[Order]] = defaultdict(list)
    for o in orders:
        by_date[o.created_at.date()].append(o)

    refreshed = 0
    for day, day_orders in by_date.items():
        gross = sum((o.grand_total for o in day_orders if o.payment_status in _PAID_STATUSES), Decimal(0))
        units = sum(items_by_order[o.id] for o in day_orders)
        day_refunds = [r for oid in [o.id for o in day_orders] for r in refunds_by_order.get(oid, [])]
        # Also count refunds issued that day regardless of which day the order was placed.
        day_refunds_by_date = [r for r in refunds if r.created_at.date() == day]
        refunds_amount = sum((r.amount for r in day_refunds_by_date), Decimal(0))
        refunds_count = len(day_refunds_by_date)
        net = gross - sum((r.amount for r in day_refunds), Decimal(0))

        users_today = {o.user_id for o in day_orders if o.user_id is not None}
        new_customers = sum(1 for u in users_today if all_user_first_order.get(u) and all_user_first_order[u].date() == day)
        returning_customers = len(users_today) - new_customers

        await session.execute(delete(DailySalesSummary).where(DailySalesSummary.date == day))
        session.add(
            DailySalesSummary(
                date=day,
                orders=len(day_orders),
                gross_revenue=gross,
                net_revenue=net,
                units=units,
                aov=(gross / len(day_orders)) if day_orders else Decimal(0),
                new_customers=new_customers,
                returning_customers=returning_customers,
                refunds_count=refunds_count,
                refunds_amount=refunds_amount,
                refreshed_at=utcnow(),
            )
        )
        refreshed += 1
    return refreshed


async def _velocity_status(days_of_cover: Decimal) -> str:
    if days_of_cover < 3:
        return "critical"
    if days_of_cover < 7:
        return "low"
    if days_of_cover < 14:
        return "watch"
    return "healthy"


async def _refresh_product_velocity(session) -> int:
    now = utcnow()
    cutoff_7 = now - timedelta(days=7)
    cutoff_30 = now - timedelta(days=30)

    variants = list((await session.execute(select(ProductVariant).where(ProductVariant.is_active))).scalars().all())

    units_7d: dict[int, int] = defaultdict(int)
    units_30d: dict[int, int] = defaultdict(int)
    revenue_7d: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    revenue_30d: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    rows = await session.execute(
        select(OrderItem.variant_id, OrderItem.quantity, OrderItem.line_total, Order.created_at)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.created_at >= cutoff_30)
    )
    for variant_id, qty, line_total, created_at in rows:
        units_30d[variant_id] += qty
        revenue_30d[variant_id] += line_total
        if created_at >= cutoff_7:
            units_7d[variant_id] += qty
            revenue_7d[variant_id] += line_total

    await session.execute(delete(ProductVelocitySummary))
    for v in variants:
        avg_daily = Decimal(units_30d.get(v.id, 0)) / Decimal(30)
        stock_qty = max(v.stock - v.reserved, 0)
        days_of_cover = min(Decimal(stock_qty) / avg_daily, Decimal(999)) if avg_daily > 0 else Decimal(999)
        session.add(
            ProductVelocitySummary(
                variant_id=v.id,
                product_id=v.product_id,
                units_7d=units_7d.get(v.id, 0),
                units_30d=units_30d.get(v.id, 0),
                revenue_7d=revenue_7d.get(v.id, Decimal(0)),
                revenue_30d=revenue_30d.get(v.id, Decimal(0)),
                avg_daily_units_30d=avg_daily.quantize(Decimal("0.01")),
                stock_qty=stock_qty,
                days_of_cover=days_of_cover.quantize(Decimal("0.01")),
                status=await _velocity_status(days_of_cover),
                refreshed_at=now,
            )
        )
    return len(variants)


async def _refresh_category_performance(session) -> int:
    cutoff = utcnow() - timedelta(days=_WINDOW_DAYS)
    rows = await session.execute(
        select(OrderItem.quantity, OrderItem.line_total, Order.created_at, Product.category_id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Order.created_at >= cutoff)
    )
    by_date_category: dict[tuple[date, int], dict] = defaultdict(lambda: {"units": 0, "revenue": Decimal(0)})
    for qty, line_total, created_at, category_id in rows:
        key = (created_at.date(), category_id)
        by_date_category[key]["units"] += qty
        by_date_category[key]["revenue"] += line_total

    return_rows = await session.execute(
        select(Return.created_at, Product.category_id)
        .join(OrderItem, Return.order_item_id == OrderItem.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Return.created_at >= cutoff)
    )
    returns_by_date_category: dict[tuple[date, int], int] = defaultdict(int)
    for created_at, category_id in return_rows:
        returns_by_date_category[(created_at.date(), category_id)] += 1

    await session.execute(delete(CategoryPerformanceSummary).where(CategoryPerformanceSummary.date >= cutoff.date()))
    for (day, category_id), agg in by_date_category.items():
        returns = returns_by_date_category.get((day, category_id), 0)
        return_rate = min(Decimal(returns) / Decimal(agg["units"]), Decimal(1)) if agg["units"] else Decimal(0)
        session.add(
            CategoryPerformanceSummary(
                date=day,
                category_id=category_id,
                units=agg["units"],
                revenue=agg["revenue"],
                return_rate=return_rate.quantize(Decimal("0.0001")),
                refreshed_at=utcnow(),
            )
        )
    return len(by_date_category)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        n_sales = await _refresh_daily_sales(session)
        n_velocity = await _refresh_product_velocity(session)
        n_category = await _refresh_category_performance(session)
        await session.commit()
        print(f"daily_sales_summary: {n_sales} day-rows")
        print(f"product_velocity_summary: {n_velocity} variant-rows")
        print(f"category_performance_summary: {n_category} date/category-rows")


if __name__ == "__main__":
    asyncio.run(main())
