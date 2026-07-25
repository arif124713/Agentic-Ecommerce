"""Password hashing/policy and JWT/opaque-token helpers (spec §11)."""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# time_cost/memory_cost/parallelism match spec §11.3 exactly (Argon2id).
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

# Precomputed hash of a random value, verified against on "unknown email" so the login
# endpoint takes the same amount of time whether or not the account exists (spec §11.4).
_DUMMY_HASH = _hasher.hash(secrets.token_hex(32))

_COMMON_PASSWORDS = {
    "password", "password123", "123456", "12345678", "qwerty", "letmein",
    "welcome", "admin123", "iloveyou", "123456789", "football", "monkey",
}

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "blackcart"
JWT_AUDIENCE = "blackcart-web"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always runs a hash verification, even for a missing user, to avoid a timing oracle."""
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
        return password_hash is not None
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, *, email: str = "", first_name: str = "") -> list[str]:
    """Spec §11.3: length, 3-of-4 character classes, common-password/name blocklist, min strength."""
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters.")
    if len(password) > 128:
        errors.append("Password must be at most 128 characters.")

    classes_present = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes_present < 3:
        errors.append("Password must contain at least 3 of: lowercase, uppercase, digit, symbol.")

    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS:
        errors.append("This password is too common. Choose something less predictable.")
    local_part = email.split("@")[0].lower() if email else ""
    if local_part and local_part in lowered:
        errors.append("Password must not contain your email address.")
    if first_name and first_name.lower() in lowered:
        errors.append("Password must not contain your name.")

    return errors


def hash_token(raw_token: str) -> str:
    """One-way hash for opaque tokens (refresh, email-verify, password-reset) stored at rest."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(*, user_public_id: str, session_id: str, roles: list[str], permissions: list[str]) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": user_public_id,
        "sid": session_id,
        "roles": roles,
        "perms": permissions,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.jwt_access_ttl_seconds),
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.app_secret_key,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except jwt.PyJWTError:
        return None


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
