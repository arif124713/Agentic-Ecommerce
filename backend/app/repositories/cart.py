import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Product, ProductVariant
from app.models.commerce import Cart, CartItem, Coupon, CouponRedemption

_CART_ITEM_LOAD_OPTIONS = (
    selectinload(Cart.items)
    .selectinload(CartItem.variant)
    .selectinload(ProductVariant.product)
    .selectinload(Product.brand),
)


class CartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_user(self, user_id: int) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.user_id == user_id, Cart.status == "active")
            .options(*_CART_ITEM_LOAD_OPTIONS)
            .order_by(Cart.id.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_active_by_session_token(self, session_token: str) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.session_token == session_token, Cart.status == "active")
            .options(*_CART_ITEM_LOAD_OPTIONS)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, cart_id: int) -> Cart | None:
        # populate_existing: this is always called right after mutating the same cart earlier
        # in the same request/session, so the identity map already holds this object with an
        # `.items` collection loaded (even if empty) — without this, SQLAlchemy's default
        # "don't clobber already-loaded state" behavior means the eager-load below is silently
        # skipped and stale (pre-mutation) items are returned instead of the fresh ones.
        stmt = (
            select(Cart)
            .where(Cart.id == cart_id)
            .options(*_CART_ITEM_LOAD_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def create(self, *, public_id: str, user_id: int | None, session_token: str | None, ttl_seconds: int) -> Cart:
        now = datetime.datetime.now(datetime.UTC)
        cart = Cart(
            public_id=public_id,
            user_id=user_id,
            session_token=session_token,
            currency="INR",
            expires_at=now + datetime.timedelta(seconds=ttl_seconds),
            created_at=now,
            updated_at=now,
            items=[],
        )
        self.session.add(cart)
        return cart

    async def get_variant_with_product(self, variant_id: int) -> ProductVariant | None:
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.id == variant_id, ProductVariant.deleted_at.is_(None))
            .options(selectinload(ProductVariant.product).selectinload(Product.brand))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_item(self, item: CartItem) -> None:
        self.session.add(item)

    async def get_coupon_by_code(self, code: str) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.code == code.upper())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_coupon_for_update(self, code: str) -> Coupon | None:
        """Locks the coupon row so concurrent checkouts can't both redeem the last unit of a
        limited coupon (spec §9.6)."""
        stmt = select(Coupon).where(Coupon.code == code.upper()).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_redemption(self, redemption: CouponRedemption) -> None:
        self.session.add(redemption)

    async def count_user_redemptions(self, coupon_id: int, user_id: int) -> int:
        stmt = select(func.count()).where(
            CouponRedemption.coupon_id == coupon_id, CouponRedemption.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one()
