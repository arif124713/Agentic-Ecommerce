"""MFA (TOTP) tests (spec §11.5, §10.8's MFA_REQUIRED flow): setup/enable/disable, the
login-time second-factor gate, and recovery-code consumption."""

import pyotp

from tests.conftest import register_and_login, unique_email


async def _setup_and_enable(client, csrf: str) -> tuple[str, list[str]]:
    """Runs /mfa/setup then /mfa/enable with a real TOTP code, returning the secret (so callers
    can keep generating valid codes) and the one-time recovery codes."""
    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers={"X-CSRF-Token": csrf})
    assert setup_resp.status_code == 200, setup_resp.text
    secret = setup_resp.json()["data"]["secret"]

    code = pyotp.TOTP(secret).now()
    enable_resp = await client.post(
        "/api/v1/auth/mfa/enable", json={"code": code}, headers={"X-CSRF-Token": csrf}
    )
    assert enable_resp.status_code == 200, enable_resp.text
    recovery_codes = enable_resp.json()["data"]["recovery_codes"]
    assert len(recovery_codes) == 10
    return secret, recovery_codes


async def test_mfa_setup_then_enable_returns_recovery_codes(client):
    creds = await register_and_login(client)
    await _setup_and_enable(client, creds["csrf"])


async def test_mfa_enable_with_wrong_code_is_rejected(client):
    creds = await register_and_login(client)
    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers={"X-CSRF-Token": creds["csrf"]})
    assert setup_resp.status_code == 200

    resp = await client.post(
        "/api/v1/auth/mfa/enable", json={"code": "000000"}, headers={"X-CSRF-Token": creds["csrf"]}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MFA_INVALID_CODE"


async def test_login_with_mfa_enabled_requires_second_factor(client):
    email = unique_email("mfa")
    creds = await register_and_login(client, email=email)
    secret, _recovery_codes = await _setup_and_enable(client, creds["csrf"])

    logout_resp = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": creds["csrf"]})
    assert logout_resp.status_code == 204

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": creds["password"]}
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "MFA_REQUIRED"
    challenge_token = login_resp.headers["x-mfa-challenge"]
    assert challenge_token

    # Not yet authenticated — no session cookie should have been issued for this attempt.
    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401

    verify_resp = await client.post(
        "/api/v1/auth/mfa/login-verify",
        json={"challenge_token": challenge_token, "code": pyotp.TOTP(secret).now()},
    )
    assert verify_resp.status_code == 200, verify_resp.text

    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == email


async def test_login_verify_with_wrong_code_is_rejected(client):
    email = unique_email("mfa")
    creds = await register_and_login(client, email=email)
    await _setup_and_enable(client, creds["csrf"])
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": creds["csrf"]})

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": creds["password"]}
    )
    challenge_token = login_resp.headers["x-mfa-challenge"]

    resp = await client.post(
        "/api/v1/auth/mfa/login-verify",
        json={"challenge_token": challenge_token, "code": "000000"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MFA_INVALID_CODE"


async def test_login_verify_with_recovery_code_consumes_it(client):
    email = unique_email("mfa")
    creds = await register_and_login(client, email=email)
    _secret, recovery_codes = await _setup_and_enable(client, creds["csrf"])
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": creds["csrf"]})

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": creds["password"]}
    )
    challenge_token = login_resp.headers["x-mfa-challenge"]
    used_code = recovery_codes[0]

    verify_resp = await client.post(
        "/api/v1/auth/mfa/login-verify",
        json={"challenge_token": challenge_token, "recovery_code": used_code},
    )
    assert verify_resp.status_code == 200, verify_resp.text

    # Second login attempt with the same already-spent recovery code must fail — one-time use.
    csrf = client.cookies.get("csrf_token")
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    login_resp_2 = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": creds["password"]}
    )
    challenge_token_2 = login_resp_2.headers["x-mfa-challenge"]
    replay_resp = await client.post(
        "/api/v1/auth/mfa/login-verify",
        json={"challenge_token": challenge_token_2, "recovery_code": used_code},
    )
    assert replay_resp.status_code == 401
    assert replay_resp.json()["error"]["code"] == "MFA_INVALID_CODE"


async def test_mfa_disable_requires_password_and_code(client):
    creds = await register_and_login(client)
    secret, _recovery_codes = await _setup_and_enable(client, creds["csrf"])

    wrong_password_resp = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "WrongPassw0rd!123", "code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": creds["csrf"]},
    )
    assert wrong_password_resp.status_code == 401

    disable_resp = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": creds["password"], "code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": creds["csrf"]},
    )
    assert disable_resp.status_code == 204

    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.json()["data"]["mfa_enabled"] is False
