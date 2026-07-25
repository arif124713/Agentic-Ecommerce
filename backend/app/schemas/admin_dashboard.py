from decimal import Decimal

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    orders_today: int
    orders_this_week: int
    revenue_today: Decimal
    revenue_this_week: Decimal
    orders_by_status: dict[str, int]
    low_stock_count: int
    total_customers: int
