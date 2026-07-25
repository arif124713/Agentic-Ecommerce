from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_cart_session_cookie, get_db, get_optional_user
from app.core.cookies import set_cart_session_cookie
from app.models.auth import User
from app.schemas.cart import ApplyCouponIn, CartItemIn, CartItemQuantityIn, CartOut
from app.services.cart_service import CartResult, CartService

router = APIRouter(prefix="/cart", tags=["cart"])


def _respond(response: Response, result: CartResult) -> CartOut:
    if result.new_session_token:
        set_cart_session_cookie(response, result.new_session_token)
    return result.cart


@router.get("", response_model=CartOut)
async def get_cart(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).get_cart(user=user, session_token=session_token)
    return _respond(response, result)


@router.post("/items", response_model=CartOut, status_code=201)
async def add_item(
    payload: CartItemIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).add_item(
        user=user, session_token=session_token, variant_id=payload.variant_id, quantity=payload.quantity
    )
    return _respond(response, result)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_item(
    item_id: int,
    payload: CartItemQuantityIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).update_item(
        user=user, session_token=session_token, item_id=item_id, quantity=payload.quantity
    )
    return _respond(response, result)


@router.delete("/items/{item_id}", response_model=CartOut)
async def remove_item(
    item_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).remove_item(user=user, session_token=session_token, item_id=item_id)
    return _respond(response, result)


@router.delete("", response_model=CartOut)
async def clear_cart(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).clear_cart(user=user, session_token=session_token)
    return _respond(response, result)


@router.post("/coupon", response_model=CartOut)
async def apply_coupon(
    payload: ApplyCouponIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).apply_coupon(user=user, session_token=session_token, code=payload.code)
    return _respond(response, result)


@router.delete("/coupon", response_model=CartOut)
async def remove_coupon(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    session_token: str | None = Depends(get_cart_session_cookie),
):
    result = await CartService(db).remove_coupon(user=user, session_token=session_token)
    return _respond(response, result)
