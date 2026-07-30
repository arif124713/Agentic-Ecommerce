from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.core.audit import AuditContext, get_audit_context
from app.models.auth import User
from app.schemas.admin_coupon import CouponOut, CouponWriteIn
from app.services.admin.coupon_service import AdminCouponService

router = APIRouter(prefix="/admin/coupons", tags=["admin-coupons"])


@router.get("", response_model=list[CouponOut])
async def list_coupons(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("promo:coupon:write")),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await AdminCouponService(db).list_coupons(page=page, per_page=per_page)
    return items


@router.get("/{coupon_id}", response_model=CouponOut)
async def get_coupon(
    coupon_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("promo:coupon:write"))
):
    return await AdminCouponService(db).get_coupon(coupon_id)


@router.post("", response_model=CouponOut, status_code=201)
async def create_coupon(
    payload: CouponWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("promo:coupon:write")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminCouponService(db).create_coupon(payload, ctx)


@router.patch("/{coupon_id}", response_model=CouponOut)
async def update_coupon(
    coupon_id: int,
    payload: CouponWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("promo:coupon:write")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminCouponService(db).update_coupon(coupon_id, payload, ctx)


@router.delete("/{coupon_id}", response_model=CouponOut)
async def deactivate_coupon(
    coupon_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("promo:coupon:write")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminCouponService(db).deactivate_coupon(coupon_id, ctx)
