"""Support tickets (spec §8.3): customer create/list/reply scoped to their own tickets only
(an IDOR surface, tested explicitly), admin list/assign/reply/status-change gated by
support:ticket:manage (spec §3.3)."""

from sqlalchemy import select

from app.core.timeutil import utcnow
from app.models.auth import Role, User, UserRole
from tests.conftest import register_and_login, unique_email


async def _promote(db_session, user_id: int, role_code: str) -> None:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role.id, granted_at=utcnow()))
    await db_session.flush()


async def _make_support_agent(client, db_session):
    creds = await register_and_login(client, email=unique_email("agent"))
    user = (await db_session.execute(select(User).where(User.email == creds["email"]))).scalar_one()
    await _promote(db_session, user.id, "support")
    await client.post("/api/v1/auth/login", json={"email": creds["email"], "password": creds["password"]})
    return user, creds


async def test_customer_can_create_and_list_own_ticket(client, db_session):
    await register_and_login(client)

    create_resp = await client.post(
        "/api/v1/support/tickets",
        json={"subject": "Order not delivered", "body": "It has been 5 days.", "priority": "high"},
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()["data"]
    assert body["status"] == "open"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["author_type"] == "customer"

    list_resp = await client.get("/api/v1/support/tickets")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1
    assert list_resp.json()["data"][0]["public_id"] == body["public_id"]


async def test_customer_cannot_view_another_users_ticket(client, db_session):
    """IDOR check, same discipline as test_auth_security.py's order/address ownership tests."""
    await register_and_login(client, email=unique_email("owner"))
    create_resp = await client.post(
        "/api/v1/support/tickets", json={"subject": "Private issue", "body": "Sensitive details."}
    )
    ticket_public_id = create_resp.json()["data"]["public_id"]

    await register_and_login(client, email=unique_email("stranger"))
    resp = await client.get(f"/api/v1/support/tickets/{ticket_public_id}")
    assert resp.status_code == 404  # not 403 — existence isn't confirmed to a non-owner either

    reply_resp = await client.post(f"/api/v1/support/tickets/{ticket_public_id}/messages", json={"body": "hi"})
    assert reply_resp.status_code == 404

    stranger_list = await client.get("/api/v1/support/tickets")
    assert stranger_list.json()["data"] == []


async def test_customer_reply_reopens_a_resolved_ticket(client, db_session):
    customer_creds = await register_and_login(client, email=unique_email("customer2"))
    create_resp = await client.post("/api/v1/support/tickets", json={"subject": "x", "body": "x"})
    public_id = create_resp.json()["data"]["public_id"]

    await _make_support_agent(client, db_session)  # switches the client's session to the agent
    resolve_resp = await client.post(f"/api/v1/admin/support/tickets/{public_id}/status", json={"status": "resolved"})
    assert resolve_resp.status_code == 200, resolve_resp.text
    assert resolve_resp.json()["data"]["status"] == "resolved"

    # switch back to the original customer's session and reply
    await client.post("/api/v1/auth/login", json={"email": customer_creds["email"], "password": customer_creds["password"]})
    reply_resp = await client.post(f"/api/v1/support/tickets/{public_id}/messages", json={"body": "Still waiting!"})
    assert reply_resp.status_code == 201, reply_resp.text
    assert reply_resp.json()["data"]["status"] == "open"  # customer reply reopens it


async def test_admin_can_list_assign_and_reply_to_tickets(client, db_session):
    customer_creds = await register_and_login(client, email=unique_email("customer"))
    create_resp = await client.post(
        "/api/v1/support/tickets", json={"subject": "Refund question", "body": "When will I get my refund?"}
    )
    public_id = create_resp.json()["data"]["public_id"]

    agent, agent_creds = await _make_support_agent(client, db_session)

    list_resp = await client.get("/api/v1/admin/support/tickets")
    assert list_resp.status_code == 200
    assert any(t["public_id"] == public_id for t in list_resp.json()["data"])

    assign_resp = await client.post(
        f"/api/v1/admin/support/tickets/{public_id}/assign", json={"assignee_user_id": agent.id}
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["data"]["assignee_user_id"] == agent.id

    reply_resp = await client.post(
        f"/api/v1/admin/support/tickets/{public_id}/messages",
        json={"body": "Refunds take 5-7 business days."},
    )
    assert reply_resp.status_code == 201, reply_resp.text
    reply_body = reply_resp.json()["data"]
    assert reply_body["status"] == "pending"  # spec-consistent auto-transition on first staff reply
    assert len(reply_body["messages"]) == 2
    assert reply_body["messages"][-1]["author_type"] == "staff"

    # the customer sees the staff reply back on their own session
    await client.post("/api/v1/auth/login", json={"email": customer_creds["email"], "password": customer_creds["password"]})
    own_view = await client.get(f"/api/v1/support/tickets/{public_id}")
    assert own_view.status_code == 200
    assert own_view.json()["data"]["status"] == "pending"
    assert len(own_view.json()["data"]["messages"]) == 2


async def test_admin_ticket_endpoints_require_permission(client, db_session):
    await register_and_login(client)  # plain customer, no support:ticket:manage
    resp = await client.get("/api/v1/admin/support/tickets")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
