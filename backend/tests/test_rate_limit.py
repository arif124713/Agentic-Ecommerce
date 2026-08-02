"""Rate limiting (spec §10.7/§22.1). Exercises the in-process "memory" backend — the default for
local dev and this test suite — not the Redis backend, which needs a live Upstash instance and is
what production actually runs (`RATE_LIMIT_BACKEND=redis`; see core/rate_limit.py's docstring)."""

from tests.conftest import unique_email


async def test_register_is_rate_limited_after_five_attempts_per_ip(client):
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Test",
                "last_name": "User",
                "email": unique_email(),
                "password": "Str0ng!Passw0rd",
            },
        )
        assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/v1/auth/register",
        json={"first_name": "Test", "last_name": "User", "email": unique_email(), "password": "Str0ng!Passw0rd"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


async def test_rate_limit_is_scoped_per_endpoint_not_global(client):
    """Exhausting the register bucket must not affect an unrelated endpoint's own bucket."""
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"first_name": "Test", "last_name": "User", "email": unique_email(), "password": "Str0ng!Passw0rd"},
        )
        assert resp.status_code == 201

    blocked = await client.post(
        "/api/v1/auth/register",
        json={"first_name": "Test", "last_name": "User", "email": unique_email(), "password": "Str0ng!Passw0rd"},
    )
    assert blocked.status_code == 429

    forgot_resp = await client.post("/api/v1/auth/password/forgot", json={"email": unique_email()})
    assert forgot_resp.status_code == 202
