from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Coupon


class AdminCouponRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self, *, page: int, per_page: int) -> tuple[list[Coupon], int]:
        stmt = select(Coupon)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Coupon.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def get_by_id(self, coupon_id: int) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.id == coupon_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.code == code.upper())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, coupon: Coupon) -> None:
        self.session.add(coupon)
