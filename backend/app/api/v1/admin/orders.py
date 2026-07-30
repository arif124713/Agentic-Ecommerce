from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.core.audit import AuditContext, get_audit_context
from app.models.auth import User
from app.schemas.admin_order import AdminOrderListItem, RefundIn, RefundOut, TransitionOrderIn
from app.schemas.order import OrderDetailOut
from app.services.order_service import OrderService

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


@router.get("", response_model=list[AdminOrderListItem])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("order:order:read_all")),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await OrderService(db).admin_list_orders(status=status, q=q, page=page, per_page=per_page)
    return items


@router.get("/{order_number}", response_model=OrderDetailOut)
async def get_order(
    order_number: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require("order:order:read_all"))
):
    return await OrderService(db).admin_get_order(order_number)


@router.post("/{order_number}/transition", response_model=OrderDetailOut)
async def transition_order(
    order_number: str,
    payload: TransitionOrderIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("order:order:transition")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await OrderService(db).admin_transition(order_number, payload.to_status, payload.reason, ctx)


@router.post("/{order_number}/refund", response_model=RefundOut)
async def refund_order(
    order_number: str,
    payload: RefundIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require("order:refund:issue")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await OrderService(db).issue_refund(order_number, payload.amount, payload.reason, user.id, ctx)
