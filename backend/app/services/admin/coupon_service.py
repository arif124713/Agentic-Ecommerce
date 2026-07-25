from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.commerce import Coupon
from app.repositories.admin_coupon import AdminCouponRepository
from app.schemas.admin_coupon import CouponOut, CouponWriteIn


class AdminCouponService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.coupons = AdminCouponRepository(session)

    async def list_coupons(self, *, page: int, per_page: int) -> tuple[list[CouponOut], int]:
        coupons, total = await self.coupons.list_all(page=page, per_page=per_page)
        return [CouponOut.model_validate(c) for c in coupons], total

    async def get_coupon(self, coupon_id: int) -> CouponOut:
        coupon = await self.coupons.get_by_id(coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon was not found.")
        return CouponOut.model_validate(coupon)

    async def create_coupon(self, payload: CouponWriteIn) -> CouponOut:
        code = payload.code.upper()
        if await self.coupons.get_by_code(code) is not None:
            raise ConflictError(f"A coupon with code {code} already exists.")

        data = payload.model_dump()
        data["code"] = code
        coupon = Coupon(**data, used_count=0)
        self.coupons.add(coupon)
        await self.session.commit()
        return CouponOut.model_validate(coupon)

    async def update_coupon(self, coupon_id: int, payload: CouponWriteIn) -> CouponOut:
        coupon = await self.coupons.get_by_id(coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon was not found.")

        code = payload.code.upper()
        existing = await self.coupons.get_by_code(code)
        if existing is not None and existing.id != coupon_id:
            raise ConflictError(f"A coupon with code {code} already exists.")

        for field, value in payload.model_dump().items():
            setattr(coupon, field, value)
        coupon.code = code
        await self.session.commit()
        return CouponOut.model_validate(coupon)

    async def deactivate_coupon(self, coupon_id: int) -> CouponOut:
        coupon = await self.coupons.get_by_id(coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon was not found.")
        coupon.is_active = False
        await self.session.commit()
        return CouponOut.model_validate(coupon)
