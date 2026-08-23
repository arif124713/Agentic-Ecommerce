import datetime
import decimal

from sqlalchemy import DECIMAL, CheckConstraint, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# chat_implementation_plan.md §6: MySQL has no native materialized view, so spec §10.1's
# `mv_daily_sales` / `mv_product_velocity` / `mv_category_performance` become plain tables,
# recomputed on a schedule (Vercel Cron -> internal refresh endpoint, no Celery per the project's
# standing decision) rather than `REFRESH MATERIALIZED VIEW`. `refreshed_at` on every row lets
# analytics-mcp's `health_`-equivalent tool report staleness instead of silently serving old data.
#
# analytics-mcp's DB role gets SELECT on these three tables ONLY — never on `orders`, `order_items`,
# `users`, or any table carrying PII. That grant is what actually enforces spec §4.4's "no PII,
# ever," independent of anything the model or the tool's Python code does.


class DailySalesSummary(Base):
    """spec §10.1's `mv_daily_sales`, backing `get_sales_summary` / `get_sales_trend` /
    `compare_periods`."""

    __tablename__ = "daily_sales_summary"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    orders: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_revenue: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    net_revenue: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    aov: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    new_customers: Mapped[int] = mapped_column(Integer, nullable=False)
    returning_customers: Mapped[int] = mapped_column(Integer, nullable=False)
    refunds_count: Mapped[int] = mapped_column(Integer, nullable=False)
    refunds_amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    refreshed_at: Mapped[datetime.datetime] = mapped_column(nullable=False)


class ProductVelocitySummary(Base):
    """spec §10.1's `mv_product_velocity`, backing `get_low_stock_products` / `get_top_products`.
    Keyed by `variant_id` (the sku-level unit BlackCart actually tracks stock at, per
    `ProductVariant.stock`) with `product_id` denormalized for category-level rollups without a
    join back through `product_variants`.

    `revenue_7d`/`revenue_30d` are NOT in spec's own `mv_product_velocity` column list, but
    `get_top_products(metric="revenue")` has no other legal data source: analytics-mcp's DB role
    can only SELECT these three summary tables (chat_implementation_plan.md §6's PII boundary), so
    it can never join back to `order_items`/`orders` to compute revenue on the fly. This column is
    what makes that spec'd tool signature actually satisfiable without breaking the boundary."""

    __tablename__ = "product_velocity_summary"

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    units_7d: Mapped[int] = mapped_column(Integer, nullable=False)
    units_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_7d: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    revenue_30d: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    avg_daily_units_30d: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_cover: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    refreshed_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('critical','low','watch','healthy')", name="ck_product_velocity_status"
        ),
        CheckConstraint("days_of_cover <= 999", name="ck_product_velocity_days_of_cover_cap"),
        Index("ix_product_velocity_product", "product_id"),
        Index("ix_product_velocity_status_cover", "status", "days_of_cover"),
    )


class CategoryPerformanceSummary(Base):
    """spec §10.1's `mv_category_performance`, backing `get_category_performance`."""

    __tablename__ = "category_performance_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[decimal.Decimal] = mapped_column(DECIMAL(14, 2), nullable=False)
    return_rate: Mapped[decimal.Decimal] = mapped_column(DECIMAL(5, 4), nullable=False)
    refreshed_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("date", "category_id", name="uq_category_performance_date_category"),
        Index("ix_category_performance_date", "date"),
    )
