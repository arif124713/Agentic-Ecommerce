"""Simulated payment gateway (spec §12). Isolated behind a Protocol, same shape as a real PSP
integration would take, so swapping in a real provider later is an adapter change — the caller
never sees the difference. Deterministic test cards mirror spec §12.3 exactly; anything else is
sampled at PAYMENT_SIMULATOR_SUCCESS_RATE. Confirmation is synchronous here rather than the
async webhook chain spec §12.5 describes (no Celery in this native-Windows setup — see done.MD)."""

import random
import secrets
from decimal import Decimal
from typing import NamedTuple, Protocol

from ulid import ULID

from app.core.config import get_settings

settings = get_settings()

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
