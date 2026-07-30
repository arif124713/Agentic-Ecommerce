"""Admin API key tests (spec §11.5): scoped, peppered-argon2 machine credentials sent as
X-API-Key, restricted from iam:*/system:* scopes, with IP allowlisting and revocation."""

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from tests.conftest import register_and_login, unique_email


async def _promote(db_session, user_id: int, role_code: str) -> None:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def _make_admin(client, db_session, role_code: str = "admin"):
    creds = await register_and_login(client, email=unique_email(role_code))
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    await _promote(db_session, user.id, role_code)
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    return user, creds


async def test_create_api_key_requires_super_admin_permission(client, db_session):
    await _make_admin(client, db_session, role_code="admin")  # admin, not super_admin
    resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "reporting bot", "scopes": ["catalog:product:read"]},
    )
    assert resp.status_code == 403


async def test_super_admin_can_create_list_and_revoke_api_key(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")

    create_resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "reporting bot", "scopes": ["catalog:product:read"]},
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()["data"]
    assert body["raw_key"].startswith("bck_")
    assert body["key_prefix"] == body["raw_key"][:12]
    public_id = body["public_id"]

    list_resp = await client.get("/api/v1/admin/api-keys")
    assert list_resp.status_code == 200
    listed = next(k for k in list_resp.json()["data"] if k["public_id"] == public_id)
    assert "raw_key" not in listed

    revoke_resp = await client.delete(f"/api/v1/admin/api-keys/{public_id}")
    assert revoke_resp.status_code == 204

    list_resp_2 = await client.get("/api/v1/admin/api-keys")
    revoked_entry = next(k for k in list_resp_2.json()["data"] if k["public_id"] == public_id)
    assert revoked_entry["revoked_at"] is not None


async def test_create_api_key_rejects_restricted_scopes(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "too powerful", "scopes": ["catalog:product:read", "iam:user:assign_role"]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_api_key_rejects_unknown_scope(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "typo scope", "scopes": ["catalog:product:reed"]},
    )
    assert resp.status_code == 422


async def test_api_key_grants_scoped_access_without_a_session(client, db_session):
    # catalog:product:write (not iam:*/system:*) so it's a scope an API key is actually
    # allowed to hold, and it's exactly what GET /admin/products requires.
    await _make_admin(client, db_session, role_code="super_admin")
    create_resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "catalog bot", "scopes": ["catalog:product:write"]},
    )
    raw_key = create_resp.json()["data"]["raw_key"]

    client.cookies.clear()  # prove this works with no session cookie at all
    resp = await client.get("/api/v1/admin/products", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200, resp.text


async def test_api_key_without_required_scope_is_forbidden(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    create_resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "narrow scope", "scopes": ["catalog:product:read"]},
    )
    raw_key = create_resp.json()["data"]["raw_key"]

    client.cookies.clear()
    resp = await client.get("/api/v1/admin/products", headers={"X-API-Key": raw_key})
    assert resp.status_code == 403


async def test_revoked_api_key_is_rejected(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    create_resp = await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "short-lived", "scopes": ["catalog:product:write"]},
    )
    body = create_resp.json()["data"]
    raw_key, public_id = body["raw_key"], body["public_id"]

    await client.delete(f"/api/v1/admin/api-keys/{public_id}")

    client.cookies.clear()
    resp = await client.get("/api/v1/admin/products", headers={"X-API-Key": raw_key})
    assert resp.status_code == 401


async def test_api_key_with_nonmatching_ip_allowlist_is_forbidden(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    create_resp = await client.post(
        "/api/v1/admin/api-keys",
        json={
            "name": "office only",
            "scopes": ["catalog:product:write"],
            "ip_allowlist": ["203.0.113.5"],
        },
    )
    raw_key = create_resp.json()["data"]["raw_key"]

    client.cookies.clear()
    resp = await client.get("/api/v1/admin/products", headers={"X-API-Key": raw_key})
    assert resp.status_code == 403


async def test_wrong_api_key_value_is_rejected(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    await client.post(
        "/api/v1/admin/api-keys",
        json={"name": "real key", "scopes": ["catalog:product:write"]},
    )

    client.cookies.clear()
    resp = await client.get("/api/v1/admin/products", headers={"X-API-Key": "bck_not-a-real-key"})
    assert resp.status_code == 401
