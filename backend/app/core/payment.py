"""Simulated payment gateway (spec §12). Isolated behind a Protocol, same shape as a real PSP
integration would take, so swapping in a real provider later is an adapter change — the caller
never sees the difference. Deterministic test cards mirror spec §12.3 exactly; anything else is
sampled at PAYMENT_SIMULATOR_SUCCESS_RATE. Card payments settle through a real, signature-verified
webhook round-trip (spec §12.5) rather than a Celery task queue (none exists in this native-Windows
setup — see done.MD for the documented tradeoff of awaiting that round-trip synchronously)."""

import hashlib
import hmac
import random
import secrets
import time
from decimal import Decimal
from typing import NamedTuple, Protocol

from ulid import ULID

from app.core.config import get_settings

settings = get_settings()

# spec §12.5 step 1: "rejects timestamps older than 5 minutes (replay protection)".
WEBHOOK_REPLAY_WINDOW_SECONDS = 300


def sign_webhook(body: bytes, *, timestamp: int | None = None) -> str:
    """Returns an `X-Signature` header value in spec §12.5's `t=<ts>,v1=<hmac_sha256>` shape,
    HMAC-SHA256 over `"{ts}.{body}"` (the same signed-payload convention real PSP webhooks like
    Stripe's use, so binding the timestamp into the signed bytes — not just checking it separately
    — is what actually prevents a captured signature from being replayed with a forged timestamp)."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode("utf-8") + body
    digest = hmac.new(settings.payment_webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    try:
        parts = dict(part.split("=", 1) for part in signature.split(","))
        ts = int(parts["t"])
        provided_v1 = parts["v1"]
    except (KeyError, ValueError):
        return False

    if abs(time.time() - ts) > WEBHOOK_REPLAY_WINDOW_SECONDS:
        return False

    expected = sign_webhook(body, timestamp=ts).split("v1=", 1)[1]
    return hmac.compare_digest(expected, provided_v1)


def generate_webhook_event_id() -> str:
    return "evt_" + secrets.token_hex(12)

_TEST_CARDS: dict[str, tuple[str, str | None, str | None]] = {
    "4242424242424242": ("succeeded", None, None),
    "4000000000000002": ("failed", "CARD_DECLINED", "Your card was declined."),
    "4000000000009995": ("failed", "INSUFFICIENT_FUNDS", "Your card has insufficient funds."),
    "4000000000000069": ("failed", "EXPIRED_CARD", "Your card has expired."),
    "4000000000003220": ("succeeded", None, None),  # spec: 3DS challenge then success — challenge step skipped
    "4000000000000119": ("failed", "GATEWAY_ERROR", "A processing error occurred. Please try again."),
}


class PaymentResult(NamedTuple):
    status: str  # "succeeded" | "failed"
    transaction_id: str
    card_last4: str | None
    card_brand: str | None
    failure_code: str | None
    failure_message: str | None


class PaymentProvider(Protocol):
    def confirm(self, *, method: str, amount: Decimal, card_number: str | None) -> PaymentResult: ...


class SimulatedProvider:
    def confirm(self, *, method: str, amount: Decimal, card_number: str | None) -> PaymentResult:
        transaction_id = "TXN" + str(ULID())[:12]

        if method == "cod":
            return PaymentResult(
                transaction_id=transaction_id,
                status="succeeded",
                card_last4=None,
                card_brand=None,
                failure_code=None,
                failure_message=None,
            )

        digits = (card_number or "").replace(" ", "")
        if digits in _TEST_CARDS:
            status, code, message = _TEST_CARDS[digits]
        else:
            success = random.random() < settings.payment_simulator_success_rate
            status = "succeeded" if success else "failed"
            code = None if success else "CARD_DECLINED"
            message = None if success else "Your card was declined."

        last4 = digits[-4:] if len(digits) >= 4 else None
        brand = "visa" if digits.startswith("4") else ("mastercard" if digits.startswith("5") else "card")
        return PaymentResult(
            transaction_id=transaction_id,
            status=status,
            card_last4=last4,
            card_brand=brand if digits else None,
            failure_code=code,
            failure_message=message,
        )


def get_payment_provider() -> PaymentProvider:
    return SimulatedProvider()


def generate_tracking_number() -> str:
    return "BC" + secrets.token_hex(5).upper()


def generate_order_number(*, created_at) -> str:
    return f"BC-{created_at:%Y%m%d}-{str(ULID())[-6:]}"


def generate_refund_transaction_id() -> str:
    return "RFD" + str(ULID())[:12]
