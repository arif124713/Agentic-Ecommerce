"""Cart & coupon integration tests (spec §9.3, §9.6, §24.3 "Pricing & cart") — driven through the
real /api/v1/cart endpoints, not the service layer directly, so the HTTP contract stays exercised."""

import datetime
from decimal import Decimal

import pytest_asyncio

from app.core.timeutil import utcnow
from app.models.commerce import Coupon
from tests.conftest import make_product_with_variant, register_and_login


async def _add_item(client, variant_id: int, quantity: int = 1):
    return await client.post("/api/v1/cart/items", json={"variant_id": variant_id, "quantity": quantity})


async def test_add_item_clamped_to_available_stock(client, db_session):
    await register_and_login(client)
    _product, variant = await make_product_with_variant(db_session, stock=3)

    resp = await _add_item(client, variant.id, quantity=10)  # 10 is the per-request schema max
    assert resp.status_code == 201, resp.text
    item = resp.json()["data"]["items"][0]
    assert item["quantity"] == 3


async def test_add_item_twice_clamped_at_ten_total(client, db_session):
    await register_and_login(client)
    _product, variant = await make_product_with_variant(db_session, stock=50)

    await _add_item(client, variant.id, quantity=6)
    resp = await _add_item(client, variant.id, quantity=6)
    assert resp.status_code == 201, resp.text
    item = resp.json()["data"]["items"][0]
    assert item["quantity"] == 10


async def test_add_out_of_stock_variant_is_rejected(client, db_session):
    await register_and_login(client)
    _product, variant = await make_product_with_variant(db_session, stock=0)

    resp = await _add_item(client, variant.id, quantity=1)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ITEM_UNAVAILABLE"


async def test_cart_mutation_returns_recalculated_line_total(client, db_session):
    await register_and_login(client)
    _product, variant = await make_product_with_variant(db_session, price="250.00", stock=20)

    resp = await _add_item(client, variant.id, quantity=3)
    item = resp.json()["data"]["items"][0]
    assert Decimal(item["line_total"]) == Decimal("750.00")
    assert Decimal(resp.json()["data"]["totals"]["subtotal"]) == Decimal("750.00")


@pytest_asyncio.fixture
async def priced_cart(client, db_session):
    """A logged-in user with one Rs. 1000 line in their cart, ready to apply a coupon to."""
    await register_and_login(client)
    _product, variant = await make_product_with_variant(db_session, price="1000.00", stock=20)
    resp = await _add_item(client, variant.id, quantity=1)
    assert resp.status_code == 201
    return client


async def _make_coupon(db_session, **overrides) -> Coupon:
    defaults = dict(
        code=overrides.pop("code", "TESTCODE"),
        discount_type="percent",
        discount_value=Decimal("10"),
        is_active=True,
        stackable=False,
        used_count=0,
    )
    defaults.update(overrides)
    coupon = Coupon(**defaults)
    db_session.add(coupon)
    await db_session.flush()
    return coupon


async def test_percent_coupon_discounts_subtotal(priced_cart, db_session):
    await _make_coupon(db_session, code="TENOFF", discount_type="percent", discount_value=Decimal("10"))

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "TENOFF"})
    assert resp.status_code == 200, resp.text
    totals = resp.json()["data"]["totals"]
    assert Decimal(totals["discount_total"]) == Decimal("100.00")
    assert Decimal(totals["estimated_total"]) == Decimal(totals["subtotal"]) - Decimal("100.00") + Decimal(
        totals["tax_total"]
    )


async def test_fixed_coupon_capped_at_subtotal(priced_cart, db_session):
    """A fixed discount larger than the cart must never take the total negative."""
    await _make_coupon(db_session, code="BIGFIXED", discount_type="fixed", discount_value=Decimal("5000"))

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "BIGFIXED"})
    assert resp.status_code == 200, resp.text
    totals = resp.json()["data"]["totals"]
    assert Decimal(totals["discount_total"]) == Decimal(totals["subtotal"])


async def test_percent_coupon_respects_max_discount_cap(priced_cart, db_session):
    await _make_coupon(
        db_session,
        code="CAPPED",
        discount_type="percent",
        discount_value=Decimal("50"),  # 50% of 1000 = 500, but capped below
        max_discount_amount=Decimal("75.00"),
    )

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "CAPPED"})
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["data"]["totals"]["discount_total"]) == Decimal("75.00")


async def test_coupon_below_min_order_amount_is_rejected(priced_cart, db_session):
    await _make_coupon(db_session, code="NEEDMORE", min_order_amount=Decimal("5000.00"))

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "NEEDMORE"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "COUPON_INVALID"


async def test_expired_coupon_is_rejected(priced_cart, db_session):
    await _make_coupon(
        db_session,
        code="STALE",
        expires_at=utcnow() - datetime.timedelta(days=1),
    )

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "STALE"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "COUPON_INVALID"


async def test_unknown_coupon_code_is_rejected(priced_cart):
    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "DOESNOTEXIST"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "COUPON_INVALID"


async def test_free_shipping_coupon_does_not_discount_cart_subtotal(priced_cart, db_session):
    """Free-shipping coupons only affect the shipping fee, computed at checkout — cart-level
    totals have no shipping_fee field at all (spec §9.1/§9.2), so applying one should leave the
    cart's discount_total at zero."""
    await _make_coupon(db_session, code="SHIPFREE", discount_type="free_shipping", discount_value=Decimal("0"))

    resp = await priced_cart.post("/api/v1/cart/coupon", json={"code": "SHIPFREE"})
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["data"]["totals"]["discount_total"]) == Decimal("0.00")
    assert resp.json()["data"]["coupon_code"] == "SHIPFREE"
