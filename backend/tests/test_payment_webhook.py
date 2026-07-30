"""Payment webhook tests (spec §12.5): HMAC signature verification, replay-window rejection,
event_id dedup, and idempotent/out-of-order-tolerant state application — exercised directly
against POST /payments/webhook/simulator rather than only through the full checkout flow, since
production checkout awaits the webhook synchronously and never exposes a payment sitting in
PROCESSING to the outside (see order_service.py's own docstring for why)."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.payment import sign_webhook
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.catalog import Product, ProductVariant
from app.models.commerce import Order, OrderItem, Payment, PaymentEvent
from tests.conftest import make_product_with_variant, register_and_login


def _order_number() -> str:
    return f"BC-T{ULID()!s}"[:24]


async def _make_processing_payment(
    session: AsyncSession, *, user_id: int, product: Product, variant: ProductVariant, quantity: int = 1
) -> tuple[Order, Payment]:
    """Directly constructs a pending_payment order + a PROCESSING payment intent, bypassing
    checkout entirely — matches test_reviews.py's own pattern of building rows directly when the
    full flow isn't what's under test."""
    now = utcnow()
    order = Order(
        order_number=_order_number(),
        user_id=user_id,
        status="pending_payment",
        payment_status="pending",
        fulfilment_status="unfulfilled",
        currency="INR",
        subtotal=variant.price * quantity,
        grand_total=variant.price * quantity,
        shipping_address_json={"line1": "123 Test Street"},
        billing_address_json={"line1": "123 Test Street"},
        customer_email="buyer@example.com",
        payment_method="card",
        created_at=now,
        updated_at=now,
    )
    session.add(order)
    await session.flush()

    session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=variant.id,
            sku_snapshot=variant.sku,
            title_snapshot=product.title,
            unit_price=variant.price,
            unit_mrp=variant.mrp,
            quantity=quantity,
            line_total=variant.price * quantity,
            created_at=now,
        )
    )

    payment = Payment(
        order_id=order.id,
        method="card",
        transaction_id=f"TXN{ULID()!s}"[:15],
        status="processing",
        amount=variant.price * quantity,
        currency="INR",
        created_at=now,
        updated_at=now,
    )
    session.add(payment)
    await session.flush()
    return order, payment


def _webhook_body(*, event_id: str, order_id: int, transaction_id: str, status: str) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": f"payment.{status}",
            "order_id": order_id,
            "transaction_id": transaction_id,
            "status": status,
            "failure_code": None,
            "failure_message": None,
        }
    ).encode("utf-8")


async def test_valid_webhook_confirms_a_processing_payment(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session, stock=5)
    order, payment = await _make_processing_payment(db_session, user_id=user.id, product=product, variant=variant)
    await db_session.commit()

    body = _webhook_body(event_id="evt_test_1", order_id=order.id, transaction_id=payment.transaction_id, status="succeeded")
    resp = await client.post(
        "/api/v1/payments/webhook/simulator",
        content=body,
        headers={"X-Signature": sign_webhook(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text

    await db_session.refresh(order)
    await db_session.refresh(payment)
    assert order.status == "confirmed"
    assert order.payment_status == "paid"
    assert payment.status == "succeeded"


async def test_duplicate_event_id_is_a_noop(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session, stock=5)
    order, payment = await _make_processing_payment(db_session, user_id=user.id, product=product, variant=variant)
    await db_session.commit()

    body = _webhook_body(event_id="evt_dedup", order_id=order.id, transaction_id=payment.transaction_id, status="succeeded")
    signature = sign_webhook(body)

    first = await client.post("/api/v1/payments/webhook/simulator", content=body, headers={"X-Signature": signature})
    assert first.status_code == 200

    second = await client.post("/api/v1/payments/webhook/simulator", content=body, headers={"X-Signature": signature})
    assert second.status_code == 200  # dedup: still 200, not reprocessed

    events = (
        (await db_session.execute(select(PaymentEvent).where(PaymentEvent.payment_id == payment.id))).scalars().all()
    )
    assert len(events) == 1  # the replay never wrote a second event row


async def test_late_processing_event_after_terminal_is_ignored(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session, stock=5)
    order, payment = await _make_processing_payment(db_session, user_id=user.id, product=product, variant=variant)
    await db_session.commit()

    succeeded_body = _webhook_body(
        event_id="evt_succeeded", order_id=order.id, transaction_id=payment.transaction_id, status="succeeded"
    )
    await client.post(
        "/api/v1/payments/webhook/simulator",
        content=succeeded_body,
        headers={"X-Signature": sign_webhook(succeeded_body)},
    )

    # A stray "processing" notification with a different event_id, arriving after the terminal
    # "succeeded" outcome already landed — must not revert the payment.
    stale_body = _webhook_body(
        event_id="evt_late_processing", order_id=order.id, transaction_id=payment.transaction_id, status="processing"
    )
    resp = await client.post(
        "/api/v1/payments/webhook/simulator",
        content=stale_body,
        headers={"X-Signature": sign_webhook(stale_body)},
    )
    assert resp.status_code == 200

    await db_session.refresh(payment)
    await db_session.refresh(order)
    assert payment.status == "succeeded"
    assert order.status == "confirmed"


async def test_invalid_signature_is_rejected(client):
    body = _webhook_body(event_id="evt_bad_sig", order_id=1, transaction_id="TXN000", status="succeeded")
    resp = await client.post(
        "/api/v1/payments/webhook/simulator", content=body, headers={"X-Signature": "t=1,v1=deadbeef"}
    )
    assert resp.status_code == 401


async def test_stale_timestamp_is_rejected(client):
    body = _webhook_body(event_id="evt_stale", order_id=1, transaction_id="TXN000", status="succeeded")
    stale_signature = sign_webhook(body, timestamp=1)  # far outside the 5-minute replay window
    resp = await client.post(
        "/api/v1/payments/webhook/simulator", content=body, headers={"X-Signature": stale_signature}
    )
    assert resp.status_code == 401


async def test_mismatched_transaction_id_is_rejected(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session, stock=5)
    order, _payment = await _make_processing_payment(db_session, user_id=user.id, product=product, variant=variant)
    await db_session.commit()

    body = _webhook_body(event_id="evt_wrong_txn", order_id=order.id, transaction_id="TXN_NOT_REAL", status="succeeded")
    resp = await client.post(
        "/api/v1/payments/webhook/simulator", content=body, headers={"X-Signature": sign_webhook(body)}
    )
    assert resp.status_code == 404
