"""The flagship spec §9.4/§24.3 scenario: "A concurrency test fires 50 simultaneous checkouts
against a variant with stock 10 and asserts exactly 10 succeed." This is the one test in the
suite that deliberately does NOT use the shared rollback-per-test `client` fixture — real row
locking under real concurrent transactions is the entire point, so it needs `real_client`'s
independent per-request DB connections (see conftest.py)."""

import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import make_product_with_variant, register_and_login

STOCK = 10
CONCURRENCY = 50


async def _prepare_client(c: AsyncClient, *, email: str, variant_id: int) -> int:
    """Registers, logs in, adds a shipping address, and puts one unit of the target variant in
    the cart. Returns the new address id. All sequential, real HTTP calls — no direct DB access —
    so this reflects exactly what production traffic building up to a flash-sale checkout would
    look like, right up until the concurrent part below."""
    await register_and_login(c, email=email)
    address_resp = await c.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Concurrency Tester",
            "phone": "+8801700000000",
            "division": "Dhaka",
            "city": "Dhaka",
            "street_line1": "1 Flash Sale Ave",
        },
    )
    assert address_resp.status_code == 201, address_resp.text
    address_id = address_resp.json()["data"]["id"]

    cart_resp = await c.post("/api/v1/cart/items", json={"variant_id": variant_id, "quantity": 1})
    assert cart_resp.status_code == 201, cart_resp.text
    return address_id


async def _checkout(c: AsyncClient, address_id: int) -> int:
    resp = await c.post(
        "/api/v1/orders",
        json={
            "shipping_address_id": address_id,
            "payment_method": "card",
            "card_number": "4242424242424242",
            "accept_terms": True,
        },
    )
    return resp.status_code


async def test_fifty_concurrent_checkouts_oversell_exactly_stock(real_client, real_db_session):
    _product, variant = await make_product_with_variant(real_db_session, stock=STOCK, price="799.00")
    await real_db_session.commit()
    variant_id = variant.id

    transport = ASGITransport(app=app)
    clients = [real_client] + [AsyncClient(transport=transport, base_url="http://test") for _ in range(CONCURRENCY - 1)]
    # Distinct simulated source IPs: 50 real flash-sale shoppers come from 50 different
    # addresses, and giving every client the same (ASGITransport's default) IP would trip the
    # per-IP register rate limit (core/rate_limit.py) after the first 5 — a rate-limiter false
    # positive, not the oversell behaviour this test exists to check.
    for i, c in enumerate(clients):
        c.headers["X-Forwarded-For"] = f"10.0.{i // 255}.{i % 255}"
    try:
        # Sequential setup: every buyer registers, adds an address, and puts one unit in their
        # cart before the sale "opens" — only the checkout call itself needs to race.
        address_ids = [
            await _prepare_client(c, email=f"flash-sale-{i}-{variant.sku}@example.com", variant_id=variant_id)
            for i, c in enumerate(clients)
        ]

        results = await asyncio.gather(
            *(_checkout(c, addr_id) for c, addr_id in zip(clients, address_ids)), return_exceptions=True
        )
    finally:
        for c in clients[1:]:  # real_client's own AsyncClient is closed by its fixture
            await c.aclose()

    exceptions = [r for r in results if isinstance(r, BaseException)]
    assert not exceptions, f"checkout requests raised instead of returning a status code: {exceptions}"

    succeeded = results.count(201)
    conflicted = results.count(409)
    assert succeeded == STOCK, f"expected exactly {STOCK} successful checkouts, got {succeeded} (results={results})"
    assert conflicted == CONCURRENCY - STOCK
    assert succeeded + conflicted == CONCURRENCY

    await real_db_session.refresh(variant)
    assert variant.stock == 0
    assert variant.reserved == 0  # this build decrements directly rather than reserve-then-commit
