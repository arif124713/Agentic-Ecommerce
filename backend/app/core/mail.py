"""Mail sending, abstracted the same way as PaymentProvider/ShippingProvider (spec §12.1) so a
real SMTP/MailHog backend is a config + adapter change. Only a console backend exists today —
no SMTP server is available in this native-Windows dev setup (see done.MD stack deviations)."""

from __future__ import annotations

from typing import Protocol

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("blackcart.mail")
settings = get_settings()


class MailBackend(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleMailBackend:
    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("mail_sent", to=to, subject=subject, body=body)


def get_mail_backend() -> MailBackend:
    return ConsoleMailBackend()


def send_verification_email(*, to: str, token: str) -> None:
    link = f"{settings.app_base_url}/auth/verify/{token}"
    get_mail_backend().send(
        to=to,
        subject="Verify your BlackCart email",
        body=f"Click to verify your account: {link}",
    )


def send_password_reset_email(*, to: str, token: str) -> None:
    link = f"{settings.app_base_url}/auth/reset/{token}"
    get_mail_backend().send(
        to=to,
        subject="Reset your BlackCart password",
        body=f"Click to reset your password: {link}",
    )
