from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.order import (
    CancelOrderIn,
    CheckoutPreviewIn,
    CheckoutPreviewOut,
    CreateOrderIn,
    OrderDetailOut,
    OrderSummaryOut,
    TrackingOut,
)
from app.services.order_service import OrderService

router = APIRouter(tags=["orders"])


@router.post("/checkout/session", response_model=CheckoutPreviewOut)
async def checkout_preview(
    payload: CheckoutPreviewIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await OrderService(db).preview(user, payload)


@router.post("/orders", response_model=OrderDetailOut, status_code=201)
async def create_order(
    payload: CreateOrderIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return await OrderService(db).create_order(user, payload, idempotency_key)


@router.get("/orders", response_model=list[OrderSummaryOut])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=50),
):
    summaries, _total = await OrderService(db).list_orders(user, page=page, per_page=per_page)
    return summaries


@router.get("/orders/{order_number}", response_model=OrderDetailOut)
async def get_order(order_number: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await OrderService(db).get_order(user, order_number)


@router.get("/orders/{order_number}/tracking", response_model=TrackingOut)
async def get_tracking(order_number: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await OrderService(db).get_tracking(user, order_number)


@router.post("/orders/{order_number}/cancel", response_model=OrderDetailOut)
async def cancel_order(
    order_number: str,
    payload: CancelOrderIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await OrderService(db).cancel_order(user, order_number, payload.reason)
