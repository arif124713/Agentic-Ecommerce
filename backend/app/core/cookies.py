"""Auth cookie helpers (spec §11.1). Access + CSRF are readable Lax cookies scoped to the
whole app; refresh is HttpOnly+Strict and scoped only to the auth path so it's never sent
to storefront/API calls that don't need it.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import get_settings

settings = get_settings()

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CART_SESSION_COOKIE = "cart_session"
REFRESH_COOKIE_PATH = f"{settings.api_prefix}/auth"


def set_cart_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        CART_SESSION_COOKIE,
        session_token,
        max_age=settings.guest_cart_cookie_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def clear_cart_session_cookie(response: Response) -> None:
    response.delete_cookie(CART_SESSION_COOKIE, domain=settings.cookie_domain, path="/")


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    refresh_max_age: int | None,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        domain=settings.cookie_domain,
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, domain=settings.cookie_domain, path="/")
    response.delete_cookie(REFRESH_COOKIE, domain=settings.cookie_domain, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, domain=settings.cookie_domain, path="/")
