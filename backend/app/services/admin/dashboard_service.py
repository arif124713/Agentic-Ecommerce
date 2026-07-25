import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.repositories.admin_catalog import AdminProductRepository
from app.repositories.admin_dashboard import AdminDashboardRepository
from app.schemas.admin_dashboard import DashboardSummaryOut


class AdminDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dashboard = AdminDashboardRepository(session)
        self.products = AdminProductRepository(session)

    async def get_summary(self) -> DashboardSummaryOut:
        now = utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - datetime.timedelta(days=today_start.weekday())

        orders_today = await self.dashboard.order_count_since(today_start)
        orders_this_week = await self.dashboard.order_count_since(week_start)
        revenue_today = await self.dashboard.revenue_since(today_start)
        revenue_this_week = await self.dashboard.revenue_since(week_start)
        orders_by_status = await self.dashboard.orders_by_status()
        low_stock_count = await self.products.count_low_stock()
        total_customers = await self.dashboard.total_customers()

        return DashboardSummaryOut(
            orders_today=orders_today,
            orders_this_week=orders_this_week,
            revenue_today=revenue_today,
            revenue_this_week=revenue_this_week,
            orders_by_status=orders_by_status,
            low_stock_count=low_stock_count,
            total_customers=total_customers,
        )
