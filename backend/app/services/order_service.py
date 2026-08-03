import asyncio
import datetime
import json
from decimal import Decimal

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditContext, to_json_safe
from app.core.config import get_settings
from app.core.errors import ConflictError, ItemUnavailableError, NotFoundError
from app.core.payment import (
    PaymentResult,
    generate_order_number,
    generate_refund_transaction_id,
    generate_tracking_number,
    generate_webhook_event_id,
    get_payment_provider,
    sign_webhook,
)
from app.core.pricing import compute_shipping_fee, compute_tax, q2
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.commerce import (
    Coupon,
    CouponRedemption,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    PaymentEvent,
    Refund,
    Shipment,
    ShipmentEvent,
)
from app.repositories.address import AddressRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository, PaymentRepository, RefundRepository, ShipmentRepository
from app.schemas.admin_order import AdminOrderListItem, RefundOut
from app.schemas.order import (
    CheckoutPreviewIn,
    CheckoutPreviewOut,
    CreateOrderIn,
    OrderDetailOut,
    OrderLineOut,
    OrderSummaryOut,
    OrderTotals,
    PaymentOut,
    ShipmentEventOut,
    TrackingOut,
)
from app.schemas.payment import PaymentWebhookEventIn

settings = get_settings()
logger = structlog.get_logger("blackcart.payment")

# spec §9.5 — the only legal transitions; system-driven fulfilment progression below is checked
# against this same table so a future admin-transition endpoint can't diverge from it.
ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending_payment": {"confirmed", "failed", "cancelled"},
    "confirmed": {"processing", "cancelled"},
    "processing": {"packed", "cancelled"},
    "packed": {"shipped"},
    "shipped": {"out_for_delivery"},
    "out_for_delivery": {"delivered", "delivery_failed"},
    "delivery_failed": {"out_for_delivery", "returned"},
    "delivered": {"return_requested"},
    "return_requested": {"return_approved", "return_rejected"},
    "return_approved": {"refunded"},
    "return_rejected": {"delivered"},
    "failed": set(),
    "cancelled": set(),
    "refunded": set(),
}
CANCELLABLE_STATUSES = {"pending_payment", "confirmed", "processing"}

# How long a paid order sits in "confirmed" before auto-advancing to "shipped" — deliberately a
# fixed real-world delay (not scaled by delivery_simulator_minutes_per_hour) so there's always a
# genuine window to test/demo customer-initiated cancellation.
PRE_SHIP_DELAY_MINUTES = 2

# spec §13.1 T+offset(hours) schedule, compressed by delivery_simulator_minutes_per_hour.
SHIPMENT_SCHEDULE = [
    (0, "label_generated", "Origin warehouse", "Shipment created, label generated"),
    (2, "picked_up", "Origin hub", "Picked up by carrier"),
    (8, "in_transit", "Sorting facility", "In transit"),
    (20, "arrived_hub", "Destination city", "Arrived at destination hub"),
    (30, "out_for_delivery", "Local depot", "Out for delivery"),
    (34, "delivered", "Customer address", "Delivered"),
]


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.orders = OrderRepository(session)
        self.payments = PaymentRepository(session)
        self.shipments = ShipmentRepository(session)
        self.refunds = RefundRepository(session)
        self.carts = CartRepository(session)
        self.addresses = AddressRepository(session)
        self.audit = AuditLogRepository(session)
        self.provider = get_payment_provider()

    # -- shared pricing/line-building --------------------------------------------------------

    async def _price_cart(
        self, cart, payment_method: str
    ) -> tuple[list[OrderLineOut], OrderTotals, Coupon | None, Decimal]:
        lines = [
            OrderLineOut(
                variant_id=i.variant_id,
                sku=i.variant.sku,
                title=i.variant.product.title,
                brand=i.variant.product.brand.name,
                image=i.variant.product.thumbnail_url,
                size=i.variant.size,
                color=i.variant.color,
                unit_price=i.variant.price,
                quantity=i.quantity,
                line_total=q2(i.variant.price * i.quantity),
            )
            for i in cart.items
        ]
        subtotal = q2(sum((line.line_total for line in lines), Decimal("0")))

        coupon = None
        discount_total = Decimal("0")
        free_shipping = False
        if cart.coupon_code:
            coupon = await self.carts.get_coupon_by_code(cart.coupon_code)
            if coupon is not None and self._coupon_still_valid(coupon, subtotal):
                if coupon.discount_type == "free_shipping":
                    free_shipping = True
                else:
                    amount = (
                        subtotal * (coupon.discount_value / Decimal(100))
                        if coupon.discount_type == "percent"
                        else coupon.discount_value
                    )
                    if coupon.max_discount_amount is not None:
                        amount = min(amount, coupon.max_discount_amount)
                    discount_total = q2(min(amount, subtotal))
            else:
                coupon = None

        shipping_fee = compute_shipping_fee(subtotal=subtotal, payment_method=payment_method, free_shipping=free_shipping)
        taxable_base = subtotal - discount_total
        tax_total = compute_tax(taxable_base)
        grand_total = q2(taxable_base + tax_total + shipping_fee)

        totals = OrderTotals(
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_fee=shipping_fee,
            tax_total=tax_total,
            grand_total=grand_total,
        )
        return lines, totals, coupon, discount_total

    def _coupon_still_valid(self, coupon: Coupon, subtotal: Decimal) -> bool:
        now = utcnow()
        if not coupon.is_active:
            return False
        if coupon.starts_at and coupon.starts_at > now:
            return False
        if coupon.expires_at and coupon.expires_at < now:
            return False
        if coupon.usage_limit_total is not None and coupon.used_count >= coupon.usage_limit_total:
            return False
        return not (coupon.min_order_amount is not None and subtotal < coupon.min_order_amount)

    def _delivery_window(self, now: datetime.datetime) -> tuple[datetime.date, datetime.date]:
        return (
            (now + datetime.timedelta(days=settings.delivery_min_days)).date(),
            (now + datetime.timedelta(days=settings.delivery_max_days)).date(),
        )

    # -- checkout preview (stateless — no reservation, no persistence) --------------------------

    async def preview(self, user: User, payload: CheckoutPreviewIn) -> CheckoutPreviewOut:
        cart = await self.carts.get_active_by_user(user.id)
        if cart is None or not cart.items:
            raise ConflictError("Your cart is empty.")
        address = await self.addresses.get_for_user(payload.shipping_address_id, user.id)
        if address is None:
            raise NotFoundError("Shipping address was not found.")

        lines, totals, _coupon, _discount = await self._price_cart(cart, payload.payment_method)
        date_from, date_to = self._delivery_window(utcnow())
        return CheckoutPreviewOut(items=lines, totals=totals, promised_delivery_from=date_from, promised_delivery_to=date_to)

    # -- order creation ------------------------------------------------------------------------

    async def create_order(self, user: User, payload: CreateOrderIn, idempotency_key: str | None) -> OrderDetailOut:
        if idempotency_key:
            existing = await self.orders.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return await self._to_detail(existing)

        if not payload.accept_terms:
            raise ConflictError("You must accept the terms to place an order.")

        cart = await self.carts.get_active_by_user(user.id)
        if cart is None or not cart.items:
            raise ConflictError("Your cart is empty.")

        shipping_address = await self.addresses.get_for_user(payload.shipping_address_id, user.id)
        if shipping_address is None:
            raise NotFoundError("Shipping address was not found.")
        billing_address = shipping_address
        if payload.billing_address_id is not None:
            maybe_billing_address = await self.addresses.get_for_user(payload.billing_address_id, user.id)
            if maybe_billing_address is None:
                raise NotFoundError("Billing address was not found.")
            billing_address = maybe_billing_address

        # Lock every distinct variant row (ordered by id) before trusting availability, so two
        # concurrent checkouts against the same low-stock variant can't both succeed (spec §9.4).
        variant_ids = sorted({i.variant_id for i in cart.items})
        locked = await self.orders.lock_variants(variant_ids)
        unavailable = [
            i.variant.sku for i in cart.items if locked.get(i.variant_id) is None or locked[i.variant_id].available < i.quantity
        ]
        if unavailable:
            raise ItemUnavailableError(
                "Some items in your cart are no longer available in the requested quantity.",
                details=[{"field": "items", "issue": sku} for sku in unavailable],
            )

        lines, totals, coupon, discount_total = await self._price_cart(cart, payload.payment_method)

        now = utcnow()
        order = Order(
            order_number=generate_order_number(created_at=now),
            user_id=user.id,
            status="pending_payment",
            payment_status="pending",
            fulfilment_status="unfulfilled",
            currency=cart.currency,
            subtotal=totals.subtotal,
            discount_total=totals.discount_total,
            shipping_fee=totals.shipping_fee,
            tax_total=totals.tax_total,
            grand_total=totals.grand_total,
            coupon_code=coupon.code if coupon else None,
            shipping_address_json=self._address_json(shipping_address),
            billing_address_json=self._address_json(billing_address),
            customer_email=user.email,
            customer_phone=shipping_address.phone,
            customer_note=payload.customer_note,
            payment_method=payload.payment_method,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            items=[],
        )
        self.orders.add(order)
        await self.session.flush()
        self.orders.add_status(
            OrderStatusHistory(
                order_id=order.id, from_status=None, to_status="pending_payment", actor_type="system", created_at=now
            )
        )

        for i in cart.items:
            self.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=i.variant.product_id,
                    variant_id=i.variant_id,
                    sku_snapshot=i.variant.sku,
                    title_snapshot=i.variant.product.title,
                    brand_snapshot=i.variant.product.brand.name,
                    image_snapshot=i.variant.product.thumbnail_url,
                    size_snapshot=i.variant.size,
                    color_snapshot=i.variant.color,
                    unit_price=i.variant.price,
                    unit_mrp=i.variant.mrp,
                    quantity=i.quantity,
                    line_total=q2(i.variant.price * i.quantity),
                    created_at=now,
                )
            )
            locked[i.variant_id].stock -= i.quantity

        if coupon is not None:
            locked_coupon = await self.carts.get_coupon_for_update(coupon.code)
            if locked_coupon is not None and self._coupon_still_valid(locked_coupon, totals.subtotal):
                locked_coupon.used_count += 1
                self.carts.add_redemption(
                    CouponRedemption(
                        coupon_id=locked_coupon.id,
                        user_id=user.id,
                        order_id=order.id,
                        discount_amount=discount_total,
                        redeemed_at=now,
                    )
                )

        result = self.provider.confirm(method=payload.payment_method, amount=totals.grand_total, card_number=payload.card_number)

        if payload.payment_method == "cod":
            # spec §12.2: "No gateway call" for COD — confirmed immediately, no webhook round-trip;
            # money is collected on delivery, not now.
            payment = Payment(
                order_id=order.id,
                method="cod",
                transaction_id=result.transaction_id,
                status="succeeded",
                amount=totals.grand_total,
                currency=order.currency,
                authorised_at=now,
                captured_at=now,
                created_at=now,
                updated_at=now,
            )
            self.payments.add(payment)
            await self.session.flush()
            self.payments.add_event(
                PaymentEvent(
                    payment_id=payment.id,
                    event_id=generate_webhook_event_id(),
                    event_type="payment.succeeded",
                    payload={"transaction_id": result.transaction_id, "method": "cod"},
                    received_at=now,
                    processed_at=now,
                )
            )
            order.payment_status = "pending"
            order.paid_total = Decimal("0")
            self._transition(order, "confirmed", actor_type="system")
            date_from, date_to = self._delivery_window(now)
            order.promised_delivery_from = date_from
            order.promised_delivery_to = date_to
            cart.status = "converted"
            cart.converted_order_id = order.id
            order.updated_at = utcnow()
            await self.session.commit()
            return await self._to_detail(await self._get_order_or_raise(order.id))

        # Card: create the payment intent in PROCESSING (spec §12.4) and commit so it's durable —
        # the webhook call below is a genuinely separate signature-verified HTTP request/response
        # cycle (spec §12.5), not a direct function call, so the order/payment rows it acts on
        # must already be visible outside this in-flight transaction.
        payment = Payment(
            order_id=order.id,
            method=payload.payment_method,
            transaction_id=result.transaction_id,
            status="processing",
            amount=totals.grand_total,
            currency=order.currency,
            card_last4=result.card_last4,
            card_brand=result.card_brand,
            created_at=now,
            updated_at=now,
        )
        self.payments.add(payment)
        await self.session.commit()

        await self._settle_card_payment_via_webhook(order_id=order.id, result=result)
        return await self._to_detail(await self._get_order_or_raise(order.id))

    async def _settle_card_payment_via_webhook(self, *, order_id: int, result: PaymentResult) -> None:
        """Builds and posts a real HMAC-signed webhook event to this same app's own
        POST /payments/webhook/simulator (spec §12.5) — a genuine signed HTTP request/response
        cycle through the full FastAPI stack (routing, signature verification, its own DB session),
        not an in-process function call. There's no Celery/Redis in this stack to fire this
        fully asynchronously on a delay, so it's awaited synchronously right here instead — a
        documented tradeoff (see done.MD): the webhook endpoint itself is fully real, idempotent,
        and replay-safe, so a genuinely delayed/retried delivery would behave identically."""
        event_body = {
            "event_id": generate_webhook_event_id(),
            "event_type": f"payment.{result.status}",
            "order_id": order_id,
            "transaction_id": result.transaction_id,
            "status": result.status,
            "failure_code": result.failure_code,
            "failure_message": result.failure_message,
        }
        body_bytes = json.dumps(event_body).encode("utf-8")
        signature = sign_webhook(body_bytes)

        from app.main import app as fastapi_app  # deferred: avoids a circular import at load time

        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://internal") as client:
            for attempt in range(3):
                try:
                    resp = await client.post(
                        f"{settings.api_prefix}/payments/webhook/simulator",
                        content=body_bytes,
                        headers={"X-Signature": signature, "Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.05 * (attempt + 1))
        logger.warning("payment_webhook_delivery_failed", order_id=order_id, transaction_id=result.transaction_id)

    async def apply_payment_webhook_event(self, payload: dict) -> None:
        """The single source of truth for applying a payment webhook's outcome (spec §12.5 steps
        3-4) — called by the webhook router, on its own DB session, exactly as a real external PSP
        callback would be. Deliberately re-derives everything it needs (payment/order/cart/stock)
        from the database rather than trusting any in-memory state from whatever request created
        the payment intent, since a real webhook can (and here, structurally does) arrive on a
        completely separate request."""
        event = PaymentWebhookEventIn.model_validate(payload)

        # spec §12.5 step 2: dedup on event_id — a replayed/duplicate delivery is a silent no-op.
        if await self.payments.get_event_by_id(event.event_id) is not None:
            return

        payment = await self.payments.get_by_order(event.order_id)
        if payment is None or payment.transaction_id != event.transaction_id:
            raise NotFoundError("No matching payment intent for this webhook event.")

        now = utcnow()
        # spec §12.5 step 3: record the event before processing — even an event this handler is
        # about to ignore (already-terminal payment) still gets a permanent audit trail entry.
        self.payments.add_event(
            PaymentEvent(
                payment_id=payment.id,
                event_id=event.event_id,
                event_type=event.event_type,
                payload=payload,
                received_at=now,
            )
        )
        await self.session.flush()

        # spec §12.5 step 4: idempotent + out-of-order tolerant — only a still-PROCESSING payment
        # can be moved to a terminal state; a "processing" (or a stray duplicate) arriving after a
        # terminal outcome is ignored rather than re-applied.
        if payment.status != "processing":
            await self.session.commit()
            return

        order = await self._get_order_or_raise(payment.order_id)

        if event.status == "succeeded":
            payment.status = "succeeded"
            payment.authorised_at = now
            payment.captured_at = now
            order.payment_status = "paid"
            order.paid_total = order.grand_total
            self._transition(order, "confirmed", actor_type="system")
            # Deliberately NOT auto-advanced to "shipped" here: spec §9.5 only allows customer
            # cancellation up through PROCESSING, so jumping straight to SHIPPED would make
            # cancellation permanently unreachable. _reconcile() advances confirmed -> processing
            # -> packed -> shipped after PRE_SHIP_DELAY_MINUTES instead — see done.MD.
            date_from, date_to = self._delivery_window(now)
            order.promised_delivery_from = date_from
            order.promised_delivery_to = date_to

            cart = await self.carts.get_active_by_user(order.user_id)
            if cart is not None:
                cart.status = "converted"
                cart.converted_order_id = order.id
        else:
            payment.status = "failed"
            payment.failed_at = now
            payment.failure_code = event.failure_code
            payment.failure_message = event.failure_message
            order.payment_status = "failed"
            self._transition(order, "failed", actor_type="system", reason=event.failure_message)

            # Release the stock decremented at order-creation time — payment didn't go through.
            # Re-locked fresh (not the caller's in-memory rows, which belong to an already-
            # committed, unrelated transaction) since a real webhook can land on any request.
            qty_by_variant: dict[int, int] = {}
            for item in order.items:
                qty_by_variant[item.variant_id] = qty_by_variant.get(item.variant_id, 0) + item.quantity
            locked = await self.orders.lock_variants(sorted(qty_by_variant))
            for variant_id, qty in qty_by_variant.items():
                if variant_id in locked:
                    locked[variant_id].stock += qty

        payment.updated_at = now
        order.updated_at = now
        await self.session.commit()

    def _transition(self, order: Order, to_status: str, *, actor_type: str, reason: str | None = None) -> None:
        allowed = ORDER_TRANSITIONS.get(order.status, set())
        if to_status not in allowed:
            raise ConflictError(f"Cannot move order from '{order.status}' to '{to_status}'.")
        from_status = order.status
        order.status = to_status
        self.orders.add_status(
            OrderStatusHistory(
                order_id=order.id,
                from_status=from_status,
                to_status=to_status,
                actor_type=actor_type,
                reason=reason,
                created_at=utcnow(),
            )
        )

    async def _ship_order(self, order: Order, now: datetime.datetime) -> None:
        """No admin ops UI exists yet to manually pick/pack/ship (Phase 4), so this runs
        automatically once _reconcile() decides PRE_SHIP_DELAY_MINUTES has passed since
        confirmation — see the comment in create_order() for why it isn't instant."""
        for status in ("processing", "packed", "shipped"):
            self._transition(order, status, actor_type="system")
        order.fulfilment_status = "fulfilled"

        tracking_number = generate_tracking_number()
        minutes_per_hour = settings.delivery_simulator_minutes_per_hour
        shipment = Shipment(
            order_id=order.id,
            tracking_number=tracking_number,
            status="in_transit",
            shipped_at=now,
            estimated_delivery_at=now + datetime.timedelta(minutes=SHIPMENT_SCHEDULE[-1][0] * minutes_per_hour),
            created_at=now,
        )
        self.shipments.add(shipment)
        await self.session.flush()
        for offset_hours, status, location, description in SHIPMENT_SCHEDULE:
            self.shipments.add_event(
                ShipmentEvent(
                    shipment_id=shipment.id,
                    status=status,
                    location=location,
                    description=description,
                    occurred_at=now + datetime.timedelta(minutes=offset_hours * minutes_per_hour),
                    created_at=now,
                )
            )

    @staticmethod
    def _address_json(address) -> dict:
        return {
            "recipient_name": address.recipient_name,
            "phone": address.phone,
            "division": address.division,
            "district": address.district,
            "city": address.city,
            "area": address.area,
            "postal_code": address.postal_code,
            "street_line1": address.street_line1,
            "street_line2": address.street_line2,
            "landmark": address.landmark,
        }

    # -- reconciliation: advance order/shipment status purely from elapsed wall-clock time -------

    async def _reconcile(self, order: Order) -> None:
        now = utcnow()

        if order.status == "confirmed":
            if (now - order.created_at).total_seconds() < PRE_SHIP_DELAY_MINUTES * 60:
                return  # still within the customer-cancellable window
            await self._ship_order(order, now)
            await self.session.commit()

        if order.status not in ("shipped", "out_for_delivery"):
            return
        shipment = await self.shipments.get_by_order(order.id)
        if shipment is None:
            return
        elapsed = [e for e in shipment.events if e.occurred_at <= now]
        if not elapsed:
            return
        latest = max(elapsed, key=lambda e: e.occurred_at)

        # Step through the state machine one edge at a time even if a lot of wall-clock time has
        # passed since this order was last viewed (e.g. no one checked it while both the
        # out_for_delivery and delivered thresholds elapsed) — ORDER_TRANSITIONS has no direct
        # shipped -> delivered edge, so skipping the intermediate step would raise a ConflictError.
        changed = False
        if order.status == "shipped" and latest.status in ("out_for_delivery", "delivered"):
            self._transition(order, "out_for_delivery", actor_type="system")
            shipment.status = "out_for_delivery"
            changed = True
        if order.status == "out_for_delivery" and latest.status == "delivered":
            self._transition(order, "delivered", actor_type="system")
            order.delivered_at = latest.occurred_at
            shipment.status = "delivered"
            shipment.delivered_at = latest.occurred_at
            changed = True
        if changed:
            await self.session.commit()

    async def _get_order_or_raise(self, order_id: int) -> Order:
        """The handful of call sites using this all re-fetch an order this same code path just
        created or already confirmed exists (by id, by FK) — never expected to actually miss, but
        `OrderRepository.get_by_id` is typed `Order | None` regardless, so this is the one place
        that narrows it rather than repeating the same not-actually-optional check everywhere."""
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} was not found.")
        return order

    # -- read models ----------------------------------------------------------------------------

    async def _to_detail(self, order: Order) -> OrderDetailOut:
        await self._reconcile(order)
        payment = await self.payments.get_by_order(order.id)
        lines = [
            OrderLineOut(
                variant_id=i.variant_id,
                sku=i.sku_snapshot,
                title=i.title_snapshot,
                brand=i.brand_snapshot,
                image=i.image_snapshot,
                size=i.size_snapshot,
                color=i.color_snapshot,
                unit_price=i.unit_price,
                quantity=i.quantity,
                line_total=i.line_total,
            )
            for i in order.items
        ]
        return OrderDetailOut(
            order_number=order.order_number,
            status=order.status,
            payment_status=order.payment_status,
            fulfilment_status=order.fulfilment_status,
            currency=order.currency,
            items=lines,
            totals=OrderTotals(
                subtotal=order.subtotal,
                discount_total=order.discount_total,
                shipping_fee=order.shipping_fee,
                tax_total=order.tax_total,
                grand_total=order.grand_total,
            ),
            shipping_address=order.shipping_address_json,
            billing_address=order.billing_address_json,
            customer_note=order.customer_note,
            payment=PaymentOut(
                method=payment.method,
                status=payment.status,
                card_last4=payment.card_last4,
                card_brand=payment.card_brand,
                transaction_id=payment.transaction_id,
                failure_code=payment.failure_code,
                failure_message=payment.failure_message,
            )
            if payment
            else None,
            promised_delivery_from=order.promised_delivery_from,
            promised_delivery_to=order.promised_delivery_to,
            delivered_at=order.delivered_at,
            cancelled_at=order.cancelled_at,
            created_at=order.created_at,
        )

    async def get_order(self, user: User, order_number: str) -> OrderDetailOut:
        order = await self.orders.get_by_order_number(order_number, user_id=user.id)
        if order is None:
            raise NotFoundError("Order was not found.")
        return await self._to_detail(order)

    async def list_orders(self, user: User, *, page: int, per_page: int) -> tuple[list[OrderSummaryOut], int]:
        orders, total = await self.orders.list_for_user(user.id, page=page, per_page=per_page)
        summaries = [
            OrderSummaryOut(
                order_number=o.order_number,
                status=o.status,
                payment_status=o.payment_status,
                currency=o.currency,
                grand_total=o.grand_total,
                item_count=sum(i.quantity for i in o.items),
                thumbnail_url=o.items[0].image_snapshot if o.items else None,
                created_at=o.created_at,
            )
            for o in orders
        ]
        return summaries, total

    async def get_tracking(self, user: User, order_number: str) -> TrackingOut:
        order = await self.orders.get_by_order_number(order_number, user_id=user.id)
        if order is None:
            raise NotFoundError("Order was not found.")
        await self._reconcile(order)
        shipment = await self.shipments.get_by_order(order.id)
        now = utcnow()
        events = (
            [
                ShipmentEventOut(status=e.status, location=e.location, description=e.description, occurred_at=e.occurred_at)
                for e in sorted(shipment.events, key=lambda e: e.occurred_at)
                if e.occurred_at <= now
            ]
            if shipment
            else []
        )
        return TrackingOut(
            order_number=order.order_number,
            tracking_number=shipment.tracking_number if shipment else None,
            carrier=shipment.carrier if shipment else None,
            shipment_status=shipment.status if shipment else None,
            estimated_delivery_at=shipment.estimated_delivery_at if shipment else None,
            delivered_at=shipment.delivered_at if shipment else None,
            events=events,
        )

    async def cancel_order(self, user: User, order_number: str, reason: str | None) -> OrderDetailOut:
        order = await self.orders.get_by_order_number(order_number, user_id=user.id)
        if order is None:
            raise NotFoundError("Order was not found.")
        if order.status not in CANCELLABLE_STATUSES:
            raise ConflictError(f"An order in status '{order.status}' can no longer be cancelled.")

        variant_ids = sorted({i.variant_id for i in order.items})
        locked = await self.orders.lock_variants(variant_ids)
        for i in order.items:
            if i.variant_id in locked:
                locked[i.variant_id].stock += i.quantity

        now = utcnow()
        self._transition(order, "cancelled", actor_type="customer", reason=reason)
        order.cancelled_at = now
        order.cancel_reason = reason
        order.updated_at = now
        await self.session.commit()
        return await self._to_detail(await self._get_order_or_raise(order.id))

    # -- admin operations -------------------------------------------------------------------------

    async def admin_list_orders(
        self, *, status: str | None, q: str | None, page: int, per_page: int
    ) -> tuple[list[AdminOrderListItem], int]:
        orders, total = await self.orders.list_all(status=status, q=q, page=page, per_page=per_page)
        items = [
            AdminOrderListItem(
                order_number=o.order_number,
                customer_email=o.customer_email,
                status=o.status,
                payment_status=o.payment_status,
                currency=o.currency,
                grand_total=o.grand_total,
                item_count=sum(i.quantity for i in o.items),
                created_at=o.created_at,
            )
            for o in orders
        ]
        return items, total

    async def admin_get_order(self, order_number: str) -> OrderDetailOut:
        order = await self.orders.get_by_order_number(order_number)
        if order is None:
            raise NotFoundError("Order was not found.")
        return await self._to_detail(order)

    async def admin_transition(
        self, order_number: str, to_status: str, reason: str | None, ctx: AuditContext
    ) -> OrderDetailOut:
        order = await self.orders.get_by_order_number(order_number)
        if order is None:
            raise NotFoundError("Order was not found.")

        before_status = order.status
        self._transition(order, to_status, actor_type="admin", reason=reason)

        if to_status == "cancelled":
            order.cancelled_at = utcnow()
            order.cancel_reason = reason
            variant_ids = sorted({i.variant_id for i in order.items})
            locked = await self.orders.lock_variants(variant_ids)
            for i in order.items:
                if i.variant_id in locked:
                    locked[i.variant_id].stock += i.quantity
        elif to_status == "delivered":
            order.delivered_at = utcnow()
        if to_status in ("shipped", "packed", "processing"):
            order.fulfilment_status = "fulfilled" if to_status == "shipped" else "unfulfilled"

        order.updated_at = utcnow()
        self.audit.record(
            ctx, action="transition", resource_type="order", resource_id=order.id,
            before={"status": before_status}, after={"status": to_status, "reason": reason},
        )
        await self.session.commit()
        return await self._to_detail(await self._get_order_or_raise(order.id))

    async def issue_refund(
        self, order_number: str, amount: Decimal, reason: str | None, actor_user_id: int, ctx: AuditContext
    ) -> RefundOut:
        order = await self.orders.get_by_order_number(order_number)
        if order is None:
            raise NotFoundError("Order was not found.")

        payment = await self.payments.get_by_order(order.id)
        if payment is None or payment.status != "succeeded":
            raise ConflictError("This order has no successful payment to refund.")

        remaining = order.paid_total - order.refunded_total
        if amount <= 0 or amount > remaining:
            raise ConflictError(f"Refund amount must be between 0 and {remaining}.")

        before_refunded_total = order.refunded_total
        now = utcnow()
        refund = Refund(
            order_id=order.id,
            payment_id=payment.id,
            amount=amount,
            reason=reason,
            status="succeeded",
            requested_by_user_id=actor_user_id,
            transaction_id=generate_refund_transaction_id(),
            processed_at=now,
            created_at=now,
        )
        self.refunds.add(refund)
        order.refunded_total += amount
        order.payment_status = "refunded" if order.refunded_total >= order.paid_total else "partially_refunded"
        order.updated_at = now
        self.audit.record(
            ctx, action="refund", resource_type="order", resource_id=order.id,
            before={"refunded_total": to_json_safe(before_refunded_total)},
            after={
                "refunded_total": to_json_safe(order.refunded_total),
                "amount": to_json_safe(amount),
                "reason": reason,
                "transaction_id": refund.transaction_id,
            },
        )
        await self.session.commit()
        return RefundOut(
            transaction_id=refund.transaction_id,
            amount=refund.amount,
            status=refund.status,
            processed_at=refund.processed_at,
        )
