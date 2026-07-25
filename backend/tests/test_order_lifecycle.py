"""Order state machine, payment outcomes, idempotency, and cancellation (spec §9.5, §12.3,
§24.3 "Order lifecycle" / "Payments")."""

import datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from app.models.commerce import Coupon, Order
from tests.conftest import make_address, make_product_with_variant, register_and_login


async def _checkout(client, address_id: int, *, payment_method: str, card_number: str | None = None, idempotency_key: str | None = None):
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    return await client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "shipping_address_id": address_id,
            "payment_method": payment_method,
            "card_number": card_number,
            "accept_terms": True,
        },
    )


async def _setup_cart_and_address(client, db_session, *, stock: int = 10, price: str = "500.00"):
    creds = await register_and_login(client)
    user_row = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    address = await make_address(db_session, user_row.id)
    _product, variant = await make_product_with_variant(db_session, price=price, stock=stock)
    resp = await client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": 1})
    assert resp.status_code == 201, resp.text
    return creds, user_row, address, variant


async def _promote(db_session, user_id: int, role_code: str) -> None:
    """Grants a role via a direct DB write, exactly like scripts/promote_admin.py does — the
    caller must log in (or re-login) AFTER this to get a fresh JWT with the new perms baked in,
    since access tokens carry a perms snapshot from login time (spec §3.2's documented gap)."""
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def test_successful_card_payment_confirms_order(client, db_session):
    _creds, _user, address, variant = await _setup_cart_and_address(client, db_session)

    resp = await _checkout(client, address.id, payment_method="card", card_number="4242424242424242")
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert order["status"] == "confirmed"
    assert order["payment_status"] == "paid"
    assert order["payment"]["status"] == "succeeded"


async def test_declined_card_fails_order_and_restores_stock(client, db_session):
    _creds, _user, address, variant = await _setup_cart_and_address(client, db_session, stock=5)

    resp = await _checkout(client, address.id, payment_method="card", card_number="4000000000000002")
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert order["status"] == "failed"
    assert order["payment"]["status"] == "failed"
    assert order["payment"]["failure_code"] == "CARD_DECLINED"

    await db_session.refresh(variant)
    assert variant.stock == 5  # decremented then released in the same request — never actually lost


async def test_cod_order_confirms_without_a_card(client, db_session):
    _creds, _user, address, _variant = await _setup_cart_and_address(client, db_session)

    resp = await _checkout(client, address.id, payment_method="cod")
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert order["status"] == "confirmed"
    assert order["payment_status"] == "pending"  # COD: money collected on delivery, not now


async def test_duplicate_idempotency_key_returns_the_same_order_once(client, db_session):
    _creds, _user, address, variant = await _setup_cart_and_address(client, db_session, stock=5)
    key = "test-idem-key-12345"

    first = await _checkout(client, address.id, payment_method="card", card_number="4242424242424242", idempotency_key=key)
    assert first.status_code == 201
    order_number = first.json()["data"]["order_number"]

    # Re-adding the same variant since the first checkout emptied the cart's line via conversion —
    # the whole point is that this second call must return the FIRST order untouched regardless.
    await client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": 1})
    second = await _checkout(client, address.id, payment_method="card", card_number="4242424242424242", idempotency_key=key)
    assert second.status_code == 201
    assert second.json()["data"]["order_number"] == order_number

    await db_session.refresh(variant)
    assert variant.stock == 4  # decremented exactly once, not twice


async def test_cancel_before_packed_restores_stock(client, db_session):
    _creds, _user, address, variant = await _setup_cart_and_address(client, db_session, stock=5)
    resp = await _checkout(client, address.id, payment_method="cod")
    order_number = resp.json()["data"]["order_number"]
    await db_session.refresh(variant)
    assert variant.stock == 4

    resp = await client.post(f"/api/v1/orders/{order_number}/cancel", json={"reason": "changed my mind"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"

    await db_session.refresh(variant)
    assert variant.stock == 5


async def test_cancel_after_shipped_is_refused(client, db_session):
    _creds, _user, address, variant = await _setup_cart_and_address(client, db_session)
    resp = await _checkout(client, address.id, payment_method="cod")
    order_number = resp.json()["data"]["order_number"]

    # Force the pre-ship delay window to have already elapsed, then GET the order once so
    # _reconcile() actually advances it (cancel_order() itself never reconciles — it only looks
    # at whatever status is already persisted, matching the real app's behaviour).
    order = (await db_session.execute(select(Order).where(Order.order_number == order_number))).scalar_one()
    order.created_at = utcnow() - datetime.timedelta(minutes=10)
    await db_session.flush()

    detail = await client.get(f"/api/v1/orders/{order_number}")
    assert detail.json()["data"]["status"] == "shipped"

    resp = await client.post(f"/api/v1/orders/{order_number}/cancel", json={})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_admin_illegal_transition_returns_409(client, db_session):
    _creds, user_row, address, _variant = await _setup_cart_and_address(client, db_session)
    resp = await _checkout(client, address.id, payment_method="cod")
    order_number = resp.json()["data"]["order_number"]  # status: confirmed

    await _promote(db_session, user_row.id, "ops_manager")
    await client.post("/api/v1/auth/login", json={"email": _creds["email"], "password": _creds["password"]})

    # confirmed -> delivered is not a legal edge (spec §9.5's ORDER_TRANSITIONS table).
    resp = await client.post(f"/api/v1/admin/orders/{order_number}/transition", json={"to_status": "delivered"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_admin_legal_transition_succeeds(client, db_session):
    _creds, user_row, address, _variant = await _setup_cart_and_address(client, db_session)
    resp = await _checkout(client, address.id, payment_method="cod")
    order_number = resp.json()["data"]["order_number"]

    await _promote(db_session, user_row.id, "ops_manager")
    await client.post("/api/v1/auth/login", json={"email": _creds["email"], "password": _creds["password"]})

    resp = await client.post(f"/api/v1/admin/orders/{order_number}/transition", json={"to_status": "processing"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "processing"


async def test_coupon_per_user_limit_blocks_reapplication_after_redemption(client, db_session):
    _creds, user_row, address, variant = await _setup_cart_and_address(client, db_session, stock=10, price="1000.00")
    coupon = Coupon(
        code="ONEUSE",
        discount_type="fixed",
        discount_value=Decimal("50"),
        usage_limit_per_user=1,
        is_active=True,
        stackable=False,
        used_count=0,
    )
    db_session.add(coupon)
    await db_session.flush()

    apply_resp = await client.post("/api/v1/cart/coupon", json={"code": "ONEUSE"})
    assert apply_resp.status_code == 200, apply_resp.text

    order_resp = await _checkout(client, address.id, payment_method="cod")
    assert order_resp.status_code == 201, order_resp.text
    assert Decimal(order_resp.json()["data"]["totals"]["discount_total"]) == Decimal("50.00")

    # A fresh cart is created on next touch (the old one converted into the order above).
    await client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": 1})
    reapply = await client.post("/api/v1/cart/coupon", json={"code": "ONEUSE"})
    assert reapply.status_code == 409
    assert reapply.json()["error"]["code"] == "COUPON_INVALID"
