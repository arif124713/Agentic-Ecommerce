"""Review eligibility, creation, moderation, and rating-aggregate recompute (spec §8.3, §9.7)."""

import decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ulid import ULID

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from app.models.catalog import Product, ProductVariant
from app.models.commerce import Order, OrderItem
from tests.conftest import make_product_with_variant, register_and_login, unique_email


def _order_number() -> str:
    return f"BC-T{ULID()!s}"[:24]


async def _make_delivered_order_item(session: AsyncSession, *, user_id: int, product: Product, variant: ProductVariant) -> OrderItem:
    """Directly constructs a DELIVERED order + line item — bypasses the checkout/payment/delivery-
    simulation flow entirely since review eligibility only cares about the end state (spec §9.7:
    "only a DELIVERED order item may be reviewed"), matching how test_order_lifecycle.py's own
    tests construct rows directly (e.g. Coupon) when the full flow isn't what's under test."""
    now = utcnow()
    order = Order(
        order_number=_order_number(),
        user_id=user_id,
        status="delivered",
        payment_status="paid",
        fulfilment_status="fulfilled",
        currency="INR",
        subtotal=variant.price,
        grand_total=variant.price,
        shipping_address_json={"line1": "123 Test Street"},
        billing_address_json={"line1": "123 Test Street"},
        customer_email="buyer@example.com",
        payment_method="cod",
        delivered_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(order)
    await session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        variant_id=variant.id,
        sku_snapshot=variant.sku,
        title_snapshot=product.title,
        unit_price=variant.price,
        unit_mrp=variant.mrp,
        quantity=1,
        line_total=variant.price,
        created_at=now,
    )
    session.add(item)
    await session.flush()
    return item


async def _promote(db_session, user_id: int, role_code: str) -> None:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def test_eligibility_lists_delivered_unreviewed_purchase(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    resp = await client.get(f"/api/v1/products/{product.slug}/reviews/eligibility")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["can_review"] is True
    assert [i["order_item_id"] for i in data["eligible_items"]] == [item.id]
    assert data["existing_review"] is None


async def test_undelivered_purchase_is_not_eligible(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)

    now = utcnow()
    order = Order(
        order_number=_order_number(),
        user_id=user.id,
        status="confirmed",
        payment_status="paid",
        fulfilment_status="unfulfilled",
        currency="INR",
        subtotal=variant.price,
        grand_total=variant.price,
        shipping_address_json={"line1": "123 Test Street"},
        billing_address_json={"line1": "123 Test Street"},
        customer_email="buyer@example.com",
        payment_method="cod",
        created_at=now,
        updated_at=now,
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=variant.id,
            sku_snapshot=variant.sku,
            title_snapshot=product.title,
            unit_price=variant.price,
            unit_mrp=variant.mrp,
            quantity=1,
            line_total=variant.price,
            created_at=now,
        )
    )
    await db_session.flush()

    resp = await client.get(f"/api/v1/products/{product.slug}/reviews/eligibility")
    assert resp.json()["data"]["can_review"] is False


async def test_create_review_then_reuse_of_same_order_item_is_rejected(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    resp = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 4, "title": "Good", "comment": "Solid purchase."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["status"] == "pending"
    assert body["is_verified_purchase"] is True
    assert body["is_own"] is True

    again = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 2, "title": "x", "comment": "x"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "REVIEW_NOT_ELIGIBLE"


async def test_review_on_undelivered_order_item_is_rejected(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)

    now = utcnow()
    order = Order(
        order_number=_order_number(),
        user_id=user.id,
        status="confirmed",
        payment_status="paid",
        fulfilment_status="unfulfilled",
        currency="INR",
        subtotal=variant.price,
        grand_total=variant.price,
        shipping_address_json={"line1": "123 Test Street"},
        billing_address_json={"line1": "123 Test Street"},
        customer_email="buyer@example.com",
        payment_method="cod",
        created_at=now,
        updated_at=now,
    )
    db_session.add(order)
    await db_session.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        variant_id=variant.id,
        sku_snapshot=variant.sku,
        title_snapshot=product.title,
        unit_price=variant.price,
        unit_mrp=variant.mrp,
        quantity=1,
        line_total=variant.price,
        created_at=now,
    )
    db_session.add(item)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 5, "title": "x", "comment": "x"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REVIEW_NOT_ELIGIBLE"


async def test_pending_review_hidden_from_other_shoppers_but_visible_to_author(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    resp = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 5, "title": "Great", "comment": "Loved it."},
    )
    assert resp.status_code == 201, resp.text

    own_view = await client.get(f"/api/v1/products/{product.slug}/reviews")
    assert own_view.json()["meta"]["total"] == 1

    # Log out (log in as a second, unrelated customer) to see the product from a stranger's view.
    other_creds = await register_and_login(client, email=unique_email("other"))
    stranger_view = await client.get(f"/api/v1/products/{product.slug}/reviews")
    assert stranger_view.json()["meta"]["total"] == 0  # pending review isn't public yet


async def test_admin_approve_recomputes_product_rating(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    create_resp = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 4, "title": "Nice", "comment": "Would recommend."},
    )
    review_id = create_resp.json()["data"]["id"]

    await _promote(db_session, user.id, "admin")
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})

    moderate_resp = await client.post(f"/api/v1/admin/reviews/{review_id}/moderate", json={"status": "approved"})
    assert moderate_resp.status_code == 200, moderate_resp.text
    assert moderate_resp.json()["data"]["status"] == "approved"

    await db_session.refresh(product)
    assert product.rating_count == 1
    assert product.review_count == 1
    assert decimal.Decimal(str(product.rating_avg)) == decimal.Decimal("4.00")

    public_view = await client.get(f"/api/v1/products/{product.slug}/reviews")
    summary = public_view.json()["summary"]
    assert summary["rating_avg"] == 4.0
    assert summary["rating_count"] == 1


async def test_eligibility_after_reviewing_two_separate_deliveries_of_same_product(client, db_session):
    """A repeat purchaser can end up with two Review rows for the same product (one per
    order_item — spec §9.7's actual granularity). The eligibility endpoint must not crash once
    both are reviewed, even though "your existing review" is now ambiguous between the two."""
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    first_item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)
    second_item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    for item in (first_item, second_item):
        resp = await client.post(
            f"/api/v1/products/{product.slug}/reviews",
            json={"order_item_id": item.id, "rating": 4, "title": "x", "comment": "x"},
        )
        assert resp.status_code == 201, resp.text

    resp = await client.get(f"/api/v1/products/{product.slug}/reviews/eligibility")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["can_review"] is False
    assert data["existing_review"] is not None


async def test_moderation_queue_requires_permission(client, db_session):
    await register_and_login(client)
    resp = await client.get("/api/v1/admin/reviews")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_edit_review_returns_it_to_pending(client, db_session):
    creds = await register_and_login(client)
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    product, variant = await make_product_with_variant(db_session)
    item = await _make_delivered_order_item(db_session, user_id=user.id, product=product, variant=variant)

    create_resp = await client.post(
        f"/api/v1/products/{product.slug}/reviews",
        json={"order_item_id": item.id, "rating": 3, "title": "Ok", "comment": "It's fine."},
    )
    review_id = create_resp.json()["data"]["id"]

    await _promote(db_session, user.id, "admin")
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    await client.post(f"/api/v1/admin/reviews/{review_id}/moderate", json={"status": "approved"})

    edit_resp = await client.patch(f"/api/v1/reviews/{review_id}", json={"rating": 5, "title": "Actually great", "comment": "Grew on me."})
    assert edit_resp.status_code == 200, edit_resp.text
    assert edit_resp.json()["data"]["status"] == "pending"  # spec §9.7: editing resets moderation

    await db_session.refresh(product)
    assert product.rating_count == 0  # the just-edited review is pending again, no longer counted
