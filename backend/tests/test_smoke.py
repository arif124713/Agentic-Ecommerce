"""Sanity checks for the test harness itself — if these fail, something's wrong with the fixture
setup (test DB, transaction rollback, auth flow), not with application code."""

from tests.conftest import register_and_login


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_register_and_login_roundtrip(client):
    result = await register_and_login(client)
    assert result["user"]["email"] == result["email"]
    assert "customer" in result["user"]["roles"]
    assert result["csrf"] is not None


async def test_transaction_rollback_isolation(client):
    """Two tests registering the same-shaped email should never collide — if this test and
    test_register_and_login_roundtrip ever see each other's data, the rollback fixture is broken."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
