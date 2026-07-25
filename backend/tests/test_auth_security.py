"""Auth & security tests (spec §11, §22, §24.3 "Auth & security"): refresh reuse detection, JWT
tampering/expiry, IDOR, CSRF, and admin permission gating."""

import datetime

import jwt

from app.core.config import get_settings
from app.core.security import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER
from tests.conftest import make_address, make_product_with_variant, register_and_login

settings = get_settings()


async def test_refresh_token_reuse_revokes_whole_family(client):
    await register_and_login(client)
    original_refresh = client.cookies.get("refresh_token")
    assert original_refresh

    # A legitimate rotation: the refresh succeeds and issues a new token.
    rotate_resp = await client.post("/api/v1/auth/refresh")
    assert rotate_resp.status_code == 200, rotate_resp.text
    rotated_refresh = client.cookies.get("refresh_token")
    assert rotated_refresh != original_refresh

    # Replaying the now-superseded original token is a reuse signal — spec §11.2 says the whole
    # family gets revoked, including the token that replay attempt would otherwise have been
    # entitled to use.
    client.cookies.set("refresh_token", original_refresh)
    reuse_resp = await client.post("/api/v1/auth/refresh")
    assert reuse_resp.status_code == 401
    assert "reuse" in reuse_resp.json()["error"]["message"].lower()

    # The legitimately-rotated token must be dead too now, not just the replayed one.
    client.cookies.set("refresh_token", rotated_refresh)
    after_reuse_resp = await client.post("/api/v1/auth/refresh")
    assert after_reuse_resp.status_code == 401


async def test_logout_revoke_is_not_flagged_as_reuse(client):
    """A token revoked by the user's own logout must not trigger the scary family-wide reuse
    response if presented again — that's just 'session is no longer valid', not an attack."""
    await register_and_login(client)
    csrf = client.cookies.get("csrf_token")
    old_refresh = client.cookies.get("refresh_token")

    logout_resp = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_resp.status_code == 204

    client.cookies.set("refresh_token", old_refresh)
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert "reuse" not in resp.json()["error"]["message"].lower()


async def test_tampered_access_token_is_rejected(client):
    await register_and_login(client)
    token = client.cookies.get("access_token")
    header_b64, payload_b64, signature_b64 = token.split(".")
    # Flip a character in the payload segment specifically, not the last character of the whole
    # token: base64url's final character sometimes has "don't care" bits, so a small fraction of
    # single-character edits right at the tail decode to the exact same bytes and leave a valid
    # signature — flaky roughly 1 run in 5 when tested against the *last* character. Any edit
    # inside the payload changes real signed bytes, so the signature check fails deterministically.
    mid = len(payload_b64) // 2
    replacement = "A" if payload_b64[mid] != "A" else "B"
    tampered_payload = payload_b64[:mid] + replacement + payload_b64[mid + 1 :]
    tampered = f"{header_b64}.{tampered_payload}.{signature_b64}"
    client.cookies.set("access_token", tampered)

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_expired_access_token_is_rejected(client):
    await register_and_login(client)
    payload = jwt.decode(
        client.cookies.get("access_token"),
        settings.app_secret_key,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )
    now = datetime.datetime.now(datetime.UTC)
    payload["iat"] = now - datetime.timedelta(hours=2)
    payload["exp"] = now - datetime.timedelta(hours=1)
    expired_token = jwt.encode(payload, settings.app_secret_key, algorithm=JWT_ALGORITHM)
    client.cookies.set("access_token", expired_token)

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_alg_none_token_is_rejected(client):
    """A classic JWT attack: re-sign the token with alg=none and no signature, hoping a lenient
    verifier accepts it. decode_access_token pins the algorithm allowlist, so this must fail."""
    await register_and_login(client)
    payload = jwt.decode(client.cookies.get("access_token"), options={"verify_signature": False})
    forged = jwt.encode(payload, key="", algorithm="none")
    client.cookies.set("access_token", forged)

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_user_cannot_read_another_users_order_by_number(client, db_session):
    creds_a = await register_and_login(client)
    user_a_addr = await _address_for(client, db_session, creds_a["email"])
    _product, variant = await make_product_with_variant(db_session, stock=5)
    await client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": 1})
    order_resp = await client.post(
        "/api/v1/orders",
        json={"shipping_address_id": user_a_addr, "payment_method": "cod", "accept_terms": True},
    )
    order_number = order_resp.json()["data"]["order_number"]

    await register_and_login(client)  # switches the same client to a brand-new user B
    resp = await client.get(f"/api/v1/orders/{order_number}")
    assert resp.status_code == 404


async def test_user_cannot_delete_another_users_address(client, db_session):
    creds_a = await register_and_login(client)
    user_a = await _user_row(db_session, creds_a["email"])
    address_a = await make_address(db_session, user_a.id)

    await register_and_login(client)  # user B
    resp = await client.delete(f"/api/v1/addresses/{address_a.id}")
    assert resp.status_code == 404


async def test_logout_without_csrf_token_is_rejected(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/auth/logout")  # no X-CSRF-Token header attached
    assert resp.status_code == 403


async def test_logout_with_csrf_token_succeeds(client):
    await register_and_login(client)
    csrf = client.cookies.get("csrf_token")
    resp = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 204


async def test_admin_route_without_permission_is_forbidden(client):
    await register_and_login(client)  # plain customer — no catalog:product:write
    resp = await client.get("/api/v1/admin/products")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_route_requires_authentication_at_all(client):
    resp = await client.get("/api/v1/admin/products")  # no login attempted
    assert resp.status_code == 401


# -- helpers ---------------------------------------------------------------------------------


async def _user_row(db_session, email: str):
    from sqlalchemy import select

    from app.models.auth import User

    return (await db_session.execute(select(User).where(User.email == email))).scalar_one()


async def _address_for(client, db_session, email: str) -> int:
    user = await _user_row(db_session, email)
    address = await make_address(db_session, user.id)
    return address.id
