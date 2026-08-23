"""analytics-mcp (chat_spec.md §4.4) — ADMIN ONLY. Every query in this module runs through
`AnalyticsSessionLocal`, bound to the `analytics_ro` MySQL role (chat_implementation_plan.md §5),
which has SELECT on `daily_sales_summary` / `product_velocity_summary` /
`category_performance_summary` and nothing else — verified empirically at M1 (see
chat_implementation_plan.md). No tool here accepts free-text SQL, and none can reach a PII table
even if it tried; that's enforced by the DB grant, not by this code.

Admin auth (spec §5.3.1's role check) happens in the FastAPI route BEFORE the agent is even
constructed (M3) — not in this module, which has no concept of "admin" at all, just a DB
connection that literally cannot see anything else.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.core.timeutil import utcnow
from app.mcp.common import analytics_session, to_jsonable
from app.models.analytics import CategoryPerformanceSummary, DailySalesSummary, ProductVelocitySummary

mcp = FastMCP(name="analytics-mcp", instructions="Read-only aggregate business analytics. Admin only.")

_PERIOD_LABELS = {
    "yesterday": "Yesterday",
    "today": "Today",
    "last_7_days": "Last 7 days",
    "last_30_days": "Last 30 days",
    "month_to_date": "Month to date",
}


def _resolve_period(period: str, start_date: str | None, end_date: str | None) -> tuple[datetime.date, datetime.date]:
    today = utcnow().date()
    if period == "yesterday":
        d = today - datetime.timedelta(days=1)
        return d, d
    if period == "today":
        return today, today
    if period == "last_7_days":
        return today - datetime.timedelta(days=6), today
    if period == "last_30_days":
        return today - datetime.timedelta(days=29), today
    if period == "month_to_date":
        return today.replace(day=1), today
    if period == "custom":
        if not start_date or not end_date:
            raise ValueError("custom period requires both start_date and end_date")
        return datetime.date.fromisoformat(start_date), datetime.date.fromisoformat(end_date)
    raise ValueError(f"Unknown period: {period}")


async def _summary_rows(session, start: datetime.date, end: datetime.date) -> list[DailySalesSummary]:
    stmt = select(DailySalesSummary).where(DailySalesSummary.date >= start, DailySalesSummary.date <= end)
    return list((await session.execute(stmt)).scalars().all())


def _aggregate(rows: list[DailySalesSummary]) -> dict:
    if not rows:
        return {
            "orders": 0, "gross_revenue": Decimal(0), "net_revenue": Decimal(0), "units": 0,
            "average_order_value": Decimal(0), "new_customers": 0, "returning_customers": 0,
            "refunds_issued": 0, "refund_amount": Decimal(0),
        }
    orders = sum(r.orders for r in rows)
    gross = sum((r.gross_revenue for r in rows), Decimal(0))
    return {
        "orders": orders,
        "gross_revenue": gross,
        "net_revenue": sum((r.net_revenue for r in rows), Decimal(0)),
        "units": sum(r.units for r in rows),
        "average_order_value": (gross / orders) if orders else Decimal(0),
        "new_customers": sum(r.new_customers for r in rows),
        "returning_customers": sum(r.returning_customers for r in rows),
        "refunds_issued": sum(r.refunds_count for r in rows),
        "refund_amount": sum((r.refunds_amount for r in rows), Decimal(0)),
    }


def _pct_change(new: Decimal, old: Decimal) -> float | None:
    if old == 0:
        return None
    return float((new - old) / old * 100)


@mcp.tool()
async def get_sales_summary(
    period: str, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """period: yesterday|today|last_7_days|last_30_days|month_to_date|custom. start_date/end_date
    (YYYY-MM-DD) required only for period="custom"."""
    start, end = _resolve_period(period, start_date, end_date)
    span_days = (end - start).days + 1
    prev_end = start - datetime.timedelta(days=1)
    prev_start = prev_end - datetime.timedelta(days=span_days - 1)

    async with analytics_session() as session:
        current = _aggregate(await _summary_rows(session, start, end))
        previous = _aggregate(await _summary_rows(session, prev_start, prev_end))

    label = _PERIOD_LABELS.get(period, f"{start.isoformat()} to {end.isoformat()}")
    return to_jsonable(
        {
            "period_label": label,
            **current,
            "currency": "BDT",
            "comparison": {
                "vs_previous_period": {
                    "orders_pct": _pct_change(Decimal(current["orders"]), Decimal(previous["orders"])),
                    "revenue_pct": _pct_change(current["gross_revenue"], previous["gross_revenue"]),
                }
            },
        }
    )


@mcp.tool()
async def get_sales_trend(granularity: str = "day", periods: int = 14) -> dict:
    """Revenue/orders trend over the last N buckets. granularity: day|week|month (week/month
    bucket by summing the underlying daily rows)."""
    periods = max(1, min(periods, 90))
    today = utcnow().date()
    bucket_days = {"day": 1, "week": 7, "month": 30}.get(granularity, 1)
    start = today - datetime.timedelta(days=bucket_days * periods - 1)

    async with analytics_session() as session:
        rows = await _summary_rows(session, start, today)

    by_date = {r.date: r for r in rows}
    buckets = []
    cursor = start
    while cursor <= today:
        bucket_end = min(cursor + datetime.timedelta(days=bucket_days - 1), today)
        in_bucket = [by_date[d] for d in by_date if cursor <= d <= bucket_end]
        agg = _aggregate(in_bucket)
        buckets.append(
            {
                "period_start": cursor.isoformat(),
                "period_end": bucket_end.isoformat(),
                "orders": agg["orders"],
                "gross_revenue": agg["gross_revenue"],
            }
        )
        cursor = bucket_end + datetime.timedelta(days=1)

    return to_jsonable({"granularity": granularity, "buckets": buckets})


@mcp.tool()
async def get_low_stock_products(threshold: int = 10, limit: int = 20, sort_by: str = "days_of_cover") -> dict:
    """Products running low, sorted by the metric a restocking decision actually needs.
    sort_by: stock|velocity|days_of_cover."""
    limit = max(1, min(limit, 100))
    async with analytics_session() as session:
        stmt = select(ProductVelocitySummary).where(ProductVelocitySummary.stock_qty <= threshold)
        if sort_by == "stock":
            stmt = stmt.order_by(ProductVelocitySummary.stock_qty.asc())
        elif sort_by == "velocity":
            stmt = stmt.order_by(ProductVelocitySummary.avg_daily_units_30d.desc())
        else:
            stmt = stmt.order_by(ProductVelocitySummary.days_of_cover.asc())
        stmt = stmt.limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())

        return to_jsonable(
            {
                "threshold": threshold,
                "products": [
                    {
                        "product_id": r.product_id,
                        "variant_id": r.variant_id,
                        "stock_remaining": r.stock_qty,
                        "avg_daily_units_30d": r.avg_daily_units_30d,
                        "days_of_cover": r.days_of_cover,
                        "status": r.status,
                        "refreshed_at": r.refreshed_at,
                    }
                    for r in rows
                ],
            }
        )


@mcp.tool()
async def get_top_products(period: str, metric: str = "revenue", limit: int = 10) -> dict:
    """Top products by revenue or units. Only "last_7_days" and "last_30_days" are meaningful
    here — the underlying summary table only tracks trailing 7d/30d windows, not arbitrary
    custom ranges (unlike get_sales_summary)."""
    limit = max(1, min(limit, 50))
    window = "7d" if period == "last_7_days" else "30d"
    units_col = ProductVelocitySummary.units_7d if window == "7d" else ProductVelocitySummary.units_30d
    revenue_col = ProductVelocitySummary.revenue_7d if window == "7d" else ProductVelocitySummary.revenue_30d
    sort_col = revenue_col if metric == "revenue" else units_col

    async with analytics_session() as session:
        stmt = select(ProductVelocitySummary).order_by(sort_col.desc()).limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())
        return to_jsonable(
            {
                "period": period,
                "metric": metric,
                "products": [
                    {
                        "product_id": r.product_id,
                        "variant_id": r.variant_id,
                        "units": r.units_7d if window == "7d" else r.units_30d,
                        "revenue": r.revenue_7d if window == "7d" else r.revenue_30d,
                    }
                    for r in rows
                ],
            }
        )


@mcp.tool()
async def get_category_performance(period: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Units/revenue/return-rate by category over a period."""
    start, end = _resolve_period(period, start_date, end_date)
    async with analytics_session() as session:
        stmt = select(CategoryPerformanceSummary).where(
            CategoryPerformanceSummary.date >= start, CategoryPerformanceSummary.date <= end
        )
        rows = list((await session.execute(stmt)).scalars().all())

    by_category: dict[int, dict] = defaultdict(lambda: {"units": 0, "revenue": Decimal(0), "weighted_returns": Decimal(0)})
    for r in rows:
        agg = by_category[r.category_id]
        agg["units"] += r.units
        agg["revenue"] += r.revenue
        agg["weighted_returns"] += Decimal(r.units) * r.return_rate

    categories = [
        {
            "category_id": cid,
            "units": agg["units"],
            "revenue": agg["revenue"],
            "return_rate": (agg["weighted_returns"] / agg["units"]) if agg["units"] else Decimal(0),
        }
        for cid, agg in by_category.items()
    ]
    categories.sort(key=lambda c: c["revenue"], reverse=True)
    return to_jsonable({"period_label": _PERIOD_LABELS.get(period, period), "categories": categories})


@mcp.tool()
async def get_returns_summary(period: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Return volume for the period, estimated from category_performance_summary's return_rate
    (units * return_rate, category-weighted) — there is no per-return-event table this role can
    reach, so this is a volume ESTIMATE, not an exact count. Use get_category_performance if a
    per-category breakdown is needed."""
    start, end = _resolve_period(period, start_date, end_date)
    async with analytics_session() as session:
        stmt = select(CategoryPerformanceSummary).where(
            CategoryPerformanceSummary.date >= start, CategoryPerformanceSummary.date <= end
        )
        rows = list((await session.execute(stmt)).scalars().all())

    total_units = sum(r.units for r in rows)
    estimated_returns = sum((Decimal(r.units) * r.return_rate for r in rows), Decimal(0))
    overall_rate = (estimated_returns / total_units) if total_units else Decimal(0)
    return to_jsonable(
        {
            "period_label": _PERIOD_LABELS.get(period, period),
            "units_sold": total_units,
            "estimated_returns": round(estimated_returns),
            "estimated_return_rate": overall_rate,
        }
    )


@mcp.tool()
async def compare_periods(metric: str, period_a: str, period_b: str) -> dict:
    """Compares one metric (orders|revenue|units|aov) between two named periods (each
    yesterday|today|last_7_days|last_30_days|month_to_date)."""
    async with analytics_session() as session:
        a_start, a_end = _resolve_period(period_a, None, None)
        b_start, b_end = _resolve_period(period_b, None, None)
        a = _aggregate(await _summary_rows(session, a_start, a_end))
        b = _aggregate(await _summary_rows(session, b_start, b_end))

    metric_key = {"orders": "orders", "revenue": "gross_revenue", "units": "units", "aov": "average_order_value"}.get(
        metric
    )
    if metric_key is None:
        return {"error": "invalid_metric", "metric": metric}

    a_val, b_val = a[metric_key], b[metric_key]
    return to_jsonable(
        {
            "metric": metric,
            "period_a": {"label": _PERIOD_LABELS.get(period_a, period_a), "value": a_val},
            "period_b": {"label": _PERIOD_LABELS.get(period_b, period_b), "value": b_val},
            "change_pct": _pct_change(Decimal(str(a_val)), Decimal(str(b_val))),
        }
    )
