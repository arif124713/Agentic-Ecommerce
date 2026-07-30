"""Admin API key generation/verification (spec §11.5): argon2(key + pepper) at rest — a slower,
peppered hash than the sha256 used for refresh/reset tokens, since a leaked key is a standing
credential rather than a short-lived session token."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

KEY_PREFIX = "bck_"
RESTRICTED_SCOPE_PREFIXES = ("iam:", "system:")


def generate_key() -> tuple[str, str]:
    """Returns (raw_key, display_prefix). The prefix is stored alongside the hash so a key can be
    identified in the admin UI without ever storing or re-displaying the raw value."""
    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return raw, raw[:12]


def hash_key(raw_key: str) -> str:
    return _hasher.hash(raw_key + settings.admin_api_key_pepper)


def verify_key(raw_key: str, key_hash: str) -> bool:
    try:
        _hasher.verify(key_hash, raw_key + settings.admin_api_key_pepper)
        return True
    except VerifyMismatchError:
        return False


def restricted_scopes(scopes: list[str]) -> list[str]:
    """Scopes that spec §11.5 forbids granting to any API key (iam:*/system:*) — checked at
    creation time so a key can never be minted with more power than a human admin session."""
    return [s for s in scopes if s.startswith(RESTRICTED_SCOPE_PREFIXES)]
