from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.config import get_settings
from app.core.errors import ConflictError, CouponInvalidError, ItemUnavailableError, NotFoundError
from app.core.pricing import compute_tax, q2
from app.core.security import generate_opaque_token
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.commerce import Cart, CartItem, Coupon
from app.repositories.cart import CartRepository
from app.schemas.cart import (
    CartItemOut,
    CartItemProductOut,
    CartItemVariantOut,
    CartOut,
    CartTotals,
)

settings = get_settings()
MAX_CART_LINES = 50


class CartResult(NamedTuple):
    cart: CartOut
    new_session_token: str | None


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.carts = CartRepository(session)

    # -- cart resolution ---------------------------------------------------------------

    async def _get_or_create_cart(self, *, user: User | None, session_token: str | None) -> tuple[Cart, str | None]:
        if user is not None:
            cart = await self.carts.get_active_by_user(user.id)
            if cart is not None:
                return cart, None
            cart = self.carts.create(
                public_id=str(ULID()), user_id=user.id, session_token=None, ttl_seconds=30 * 24 * 3600
            )
            await self.session.flush()
            return cart, None

        if session_token:
            cart = await self.carts.get_active_by_session_token(session_token)
            if cart is not None:
                return cart, None

        new_token = generate_opaque_token()
        cart = self.carts.create(
            public_id=str(ULID()),
            user_id=None,
            session_token=new_token,
            ttl_seconds=settings.guest_cart_cookie_ttl_seconds,
        )
        await self.session.flush()
        return cart, new_token

    # -- pricing -------------------------------------------------------------------------

    def _coupon_error(self, coupon: Coupon, subtotal: Decimal) -> str | None:
        now = utcnow()
        if not coupon.is_active:
            return "This coupon is no longer active."
        if coupon.starts_at and coupon.starts_at > now:
            return "This coupon isn't active yet."
        if coupon.expires_at and coupon.expires_at < now:
            return "This coupon has expired."
        if coupon.usage_limit_total is not None and coupon.used_count >= coupon.usage_limit_total:
            return "This coupon has reached its usage limit."
        if coupon.min_order_amount is not None and subtotal < coupon.min_order_amount:
            return f"Add items worth {coupon.min_order_amount} more to use this coupon."
        return None

    def _coupon_discount(self, coupon: Coupon, subtotal: Decimal) -> Decimal:
        if coupon.discount_type == "percent":
            amount = subtotal * (coupon.discount_value / Decimal(100))
        elif coupon.discount_type == "fixed":
            amount = coupon.discount_value
        else:  # free_shipping — handled at checkout time, no subtotal discount here
            return Decimal("0")
        if coupon.max_discount_amount is not None:
            amount = min(amount, coupon.max_discount_amount)
        return q2(min(amount, subtotal))

    async def _totals(self, cart: Cart) -> tuple[CartTotals, str | None]:
        subtotal = sum((i.variant.price * i.quantity for i in cart.items), Decimal("0"))
        coupon_error = None
        discount_total = Decimal("0")

        if cart.coupon_code:
            coupon = await self.carts.get_coupon_by_code(cart.coupon_code)
            if coupon is None:
                coupon_error = "This coupon is no longer available."
            else:
                coupon_error = self._coupon_error(coupon, subtotal)
                if coupon_error is None:
                    discount_total = self._coupon_discount(coupon, subtotal)

        taxable_base = subtotal - discount_total
        tax_total = compute_tax(taxable_base)
        estimated_total = q2(taxable_base + tax_total)

        return (
            CartTotals(
                subtotal=q2(subtotal),
                discount_total=q2(discount_total),
                tax_total=tax_total,
                estimated_total=estimated_total,
            ),
            coupon_error,
        )

    async def _to_out(self, cart: Cart) -> CartOut:
        totals, coupon_error = await self._totals(cart)
        items = [
            CartItemOut(
                id=i.id,
                variant_id=i.variant_id,
                variant=CartItemVariantOut(
                    sku=i.variant.sku, size=i.variant.size, color=i.variant.color, color_hex=i.variant.color_hex
                ),
                product=CartItemProductOut(
                    slug=i.variant.product.slug,
                    title=i.variant.product.title,
                    brand=i.variant.product.brand.name,
                    thumbnail_url=i.variant.product.thumbnail_url,
                ),
                quantity=i.quantity,
                unit_price=i.variant.price,
                unit_price_snapshot=i.unit_price_snapshot,
                price_changed=i.variant.price != i.unit_price_snapshot,
                available=i.variant.available,
                is_active=i.variant.is_active,
                line_total=q2(i.variant.price * i.quantity),
            )
            for i in cart.items
        ]
        return CartOut(
            public_id=cart.public_id,
            currency=cart.currency,
            items=items,
            coupon_code=cart.coupon_code,
            coupon_error=coupon_error,
            totals=totals,
        )

    async def _reload(self, cart_id: int) -> Cart:
        cart = await self.carts.get_by_id(cart_id)
        assert cart is not None  # just committed/flushed under the same transaction
        return cart

    # -- public API ------------------------------------------------------------------------

    async def get_cart(self, *, user: User | None, session_token: str | None) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        if new_token:
            await self.session.commit()
        return CartResult(await self._to_out(cart), new_token)

    async def add_item(self, *, user: User | None, session_token: str | None, variant_id: int, quantity: int) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)

        variant = await self.carts.get_variant_with_product(variant_id)
        if variant is None or not variant.is_active or variant.available <= 0:
            raise ItemUnavailableError()

        now = utcnow()
        existing = next((i for i in cart.items if i.variant_id == variant_id), None)
        if existing is not None:
            new_qty = min(existing.quantity + quantity, 10, variant.available)
            if new_qty <= 0:
                raise ItemUnavailableError()
            existing.quantity = new_qty
            existing.updated_at = now
        else:
            if len(cart.items) >= MAX_CART_LINES:
                raise ConflictError("This cart has reached the maximum number of different items.")
            qty = min(quantity, variant.available, 10)
            self.carts.add_item(
                CartItem(
                    cart_id=cart.id,
                    variant_id=variant.id,
                    quantity=qty,
                    unit_price_snapshot=variant.price,
                    added_at=now,
                    updated_at=now,
                )
            )
        cart.updated_at = now
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def update_item(
        self, *, user: User | None, session_token: str | None, item_id: int, quantity: int
    ) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        item = next((i for i in cart.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("Cart item was not found.")
        if not item.variant.is_active or item.variant.available <= 0:
            raise ItemUnavailableError()

        item.quantity = min(quantity, item.variant.available, 10)
        item.updated_at = utcnow()
        cart.updated_at = item.updated_at
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def remove_item(self, *, user: User | None, session_token: str | None, item_id: int) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        item = next((i for i in cart.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("Cart item was not found.")

        await self.session.delete(item)
        cart.updated_at = utcnow()
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def clear_cart(self, *, user: User | None, session_token: str | None) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        for item in list(cart.items):
            await self.session.delete(item)
        cart.coupon_code = None
        cart.updated_at = utcnow()
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def apply_coupon(
        self, *, user: User | None, session_token: str | None, code: str
    ) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        coupon = await self.carts.get_coupon_by_code(code)
        if coupon is None:
            raise CouponInvalidError("This coupon code doesn't exist.")

        subtotal = sum((i.variant.price * i.quantity for i in cart.items), Decimal("0"))
        error = self._coupon_error(coupon, subtotal)
        if error is None and user is not None and coupon.usage_limit_per_user is not None:
            used = await self.carts.count_user_redemptions(coupon.id, user.id)
            if used >= coupon.usage_limit_per_user:
                error = "You've already used this coupon."
        if error:
            raise CouponInvalidError(error)

        cart.coupon_code = coupon.code
        cart.updated_at = utcnow()
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def remove_coupon(self, *, user: User | None, session_token: str | None) -> CartResult:
        cart, new_token = await self._get_or_create_cart(user=user, session_token=session_token)
        cart.coupon_code = None
        cart.updated_at = utcnow()
        await self.session.commit()
        return CartResult(await self._to_out(await self._reload(cart.id)), new_token)

    async def merge_guest_into_user(self, *, session_token: str | None, user: User) -> None:
        """Spec §9.3: union by variant; quantity = min(guest+user, 10, available_stock). Called
        right after login, before the guest cookie is cleared."""
        if not session_token:
            return
        guest_cart = await self.carts.get_active_by_session_token(session_token)
        if guest_cart is None or not guest_cart.items:
            return

        user_cart = await self.carts.get_active_by_user(user.id)
        if user_cart is None:
            # No existing cart to merge into — just hand the guest cart over to the user.
            guest_cart.user_id = user.id
            guest_cart.session_token = None
            guest_cart.updated_at = utcnow()
            await self.session.commit()
            return

        user_items_by_variant = {i.variant_id: i for i in user_cart.items}
        for guest_item in list(guest_cart.items):
            available = guest_item.variant.available
            existing = user_items_by_variant.get(guest_item.variant_id)
            if existing is not None:
                existing.quantity = min(existing.quantity + guest_item.quantity, 10, available)
                existing.updated_at = utcnow()
            elif available > 0:
                self.carts.add_item(
                    CartItem(
                        cart_id=user_cart.id,
                        variant_id=guest_item.variant_id,
                        quantity=min(guest_item.quantity, 10, available),
                        unit_price_snapshot=guest_item.variant.price,
                        added_at=utcnow(),
                        updated_at=utcnow(),
                    )
                )
            await self.session.delete(guest_item)

        guest_cart.status = "merged"
        user_cart.updated_at = utcnow()
        await self.session.commit()
