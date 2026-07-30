"""Every admin mutation writes an audit_logs row with a before/after diff (spec §22.6),
inside the same transaction as the change it records. Feature flags (spec §28) are covered here
too since both are System-area admin features gated by adjacent permissions."""

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from tests.conftest import make_product_with_variant, register_and_login, unique_email


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


async def test_inventory_adjust_writes_audit_log_with_before_after_stock(client, db_session):
    await _make_admin(client, db_session)
    product, variant = await make_product_with_variant(db_session, stock=10)

    resp = await client.post(
        f"/api/v1/admin/inventory/{variant.id}/adjust", json={"delta": 5, "reason": "restock", "note": "test"}
    )
    assert resp.status_code == 200, resp.text

    logs_resp = await client.get("/api/v1/admin/audit-logs", params={"resource_type": "product_variant"})
    assert logs_resp.status_code == 200, logs_resp.text
    logs = logs_resp.json()["data"]
    entry = next(log for log in logs if log["resource_id"] == str(variant.id) and log["action"] == "adjust_inventory")
    assert entry["before_json"] == {"stock": 10}
    assert entry["after_json"]["stock"] == 15
    assert entry["after_json"]["delta"] == 5
    assert entry["actor_role"] is not None and "admin" in entry["actor_role"]


async def test_product_update_writes_audit_log_diff(client, db_session):
    await _make_admin(client, db_session)
    product, _variant = await make_product_with_variant(db_session, price="500.00")

    payload = {
        "title": product.title,
        "brand_id": product.brand_id,
        "category_id": product.category_id,
        "currency": "INR",
        "mrp": "999.00",
        "price": "750.00",
        "status": "active",
    }
    resp = await client.patch(f"/api/v1/admin/products/{product.id}", json=payload)
    assert resp.status_code == 200, resp.text

    logs_resp = await client.get("/api/v1/admin/audit-logs", params={"resource_type": "product"})
    entry = next(log for log in logs_resp.json()["data"] if log["resource_id"] == str(product.id))
    assert entry["action"] == "update"
    assert entry["before_json"]["price"] == "500.00"
    assert entry["after_json"]["price"] == "750.00"


async def test_role_grant_and_revoke_write_audit_logs(client, db_session):
    admin, admin_creds = await _make_admin(client, db_session, role_code="super_admin")
    target_creds = await register_and_login(client, email=unique_email("target"))
    target = (await db_session.execute(select(User).where(User.email == target_creds["email"]))).scalar_one()

    # register_and_login above switched the client's session to the newly-created target account —
    # switch back to the admin's own session before making the role-grant call as the admin.
    await client.post("/api/v1/auth/login", json={"email": admin_creds["email"], "password": admin_creds["password"]})

    grant_resp = await client.post(f"/api/v1/admin/users/{target.public_id}/roles", json={"role_code": "support"})
    assert grant_resp.status_code == 200, grant_resp.text

    revoke_resp = await client.delete(f"/api/v1/admin/users/{target.public_id}/roles/support")
    assert revoke_resp.status_code == 200, revoke_resp.text

    logs_resp = await client.get("/api/v1/admin/audit-logs", params={"resource_type": "user"})
    actions = [log["action"] for log in logs_resp.json()["data"] if log["resource_id"] == str(target.id)]
    assert "assign_role" in actions
    assert "revoke_role" in actions


async def test_audit_log_viewer_requires_permission(client, db_session):
    await register_and_login(client)  # plain customer
    resp = await client.get("/api/v1/admin/audit-logs")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_role_can_read_audit_logs_but_not_feature_flags(client, db_session):
    """spec §3.3's matrix: system:audit_log:read is granted to admin+super_admin, but
    system:feature_flag:write is super_admin only — the strictest permission in the matrix."""
    await _make_admin(client, db_session, role_code="admin")

    audit_resp = await client.get("/api/v1/admin/audit-logs")
    assert audit_resp.status_code == 200

    flags_resp = await client.get("/api/v1/admin/feature-flags")
    assert flags_resp.status_code == 403


async def test_super_admin_can_create_and_update_a_feature_flag(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")

    create_resp = await client.post(
        "/api/v1/admin/feature-flags",
        json={"key": "promo.flash_sale", "enabled": False, "rollout_percent": 0},
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["data"]["enabled"] is False

    update_resp = await client.patch(
        "/api/v1/admin/feature-flags/promo.flash_sale",
        json={"enabled": True, "rollout_percent": 50},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["data"]["enabled"] is True
    assert update_resp.json()["data"]["rollout_percent"] == 50

    logs_resp = await client.get("/api/v1/admin/audit-logs", params={"resource_type": "feature_flag"})
    entry = next(log for log in logs_resp.json()["data"] if log["resource_id"] == "promo.flash_sale")
    assert entry["action"] == "update"
    assert entry["before_json"]["enabled"] is False
    assert entry["after_json"]["enabled"] is True


async def test_duplicate_feature_flag_key_is_rejected(client, db_session):
    await _make_admin(client, db_session, role_code="super_admin")
    payload = {"key": "promo.duplicate_test", "enabled": True}
    first = await client.post("/api/v1/admin/feature-flags", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/admin/feature-flags", json=payload)
    assert second.status_code == 409
