import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.commerce import Order


class AdminDashboardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def order_count_since(self, since: datetime.datetime) -> int:
        stmt = select(func.count()).where(Order.created_at >= since)
        return (await self.session.execute(stmt)).scalar_one()

    async def revenue_since(self, since: datetime.datetime) -> Decimal:
        stmt = select(func.coalesce(func.sum(Order.grand_total), 0)).where(
            Order.created_at >= since, Order.status.not_in(("failed", "cancelled"))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def orders_by_status(self) -> dict[str, int]:
        stmt = select(Order.status, func.count()).group_by(Order.status)
        return dict((await self.session.execute(stmt)).all())

    async def total_customers(self) -> int:
        stmt = select(func.count()).where(User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one()
