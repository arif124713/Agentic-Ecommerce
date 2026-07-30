"""TOTP MFA helpers (spec §11.5, §8.3). `mfa_secret` is stored encrypted-at-rest (not hashed —
unlike a password, TOTP verification needs the raw secret back), using a Fernet key derived from
`APP_SECRET_KEY` so no separate KMS/secret store is needed in this stack. Recovery codes are
genuinely one-way hashed (reusing `core.security.hash_token`'s sha256, same as refresh/reset
tokens) since they're single-use and never need to be recovered, only matched."""

import base64
import hashlib
import io
import secrets

import pyotp
import qrcode
from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()

ISSUER_NAME = "BlackCart"
RECOVERY_CODE_COUNT = 10


def _fernet() -> Fernet:
    # Fernet requires a 32-byte, base64-encoded key; derive one deterministically from the app's
    # existing secret so there's nothing new to provision or rotate separately.
    key_material = hashlib.sha256(settings.app_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def generate_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def provisioning_uri(secret: str, *, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER_NAME)


def qr_data_uri(uri: str) -> str:
    """Renders the otpauth:// URI as a QR code PNG, returned as a data: URI so the frontend can
    drop it straight into an <img src>  without a client-side QR-rendering library."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret: str, code: str) -> bool:
    # valid_window=1 tolerates one 30s step of clock drift either side, matching how most real
    # authenticator apps are actually used without being so wide it weakens the six-digit code.
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(n)]
