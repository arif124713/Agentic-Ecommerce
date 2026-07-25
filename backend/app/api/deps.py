import hashlib
import secrets
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE, CART_SESSION_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.auth import User
from app.repositories.auth import UserRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent_hash(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return hashlib.sha256(ua.encode("utf-8")).hexdigest() if ua else None


def get_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE)


def get_cart_session_cookie(request: Request) -> str | None:
    return request.cookies.get(CART_SESSION_COOKIE)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise UnauthorizedError("Authentication is required.")

    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("Your session has expired. Please sign in again.")

    user = await UserRepository(db).get_by_public_id(payload["sub"])
    if user is None or user.status != "active":
        raise UnauthorizedError("Your session is no longer valid.")
    return user


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    """Same resolution as get_current_user but never raises — cart/checkout endpoints must
    work for guests too, and only escalate to a hard 401 where login is actually required."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user = await UserRepository(db).get_by_public_id(payload["sub"])
    if user is None or user.status != "active":
        return None
    return user


def get_current_session_id(request: Request) -> str | None:
    """Best-effort family id (the JWT's `sid` claim) for flagging "this device" in the
    sessions list — never raises, since it's cosmetic rather than an auth gate."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    payload = decode_access_token(token)
    return payload.get("sid") if payload else None


def require(*permissions: str):
    """Spec §3.2's `require(*permissions)` dependency. Resolves granted permissions from the
    access-token JWT's `perms` claim (set at login/refresh — see core/security.py) rather than a
    Redis-cached role lookup, since there's no Redis here; this bounds a permission change's
    propagation delay to one access-token lifetime (15 min) instead of instant revocation, a
    documented gap (see done.MD's perm_ver note from Phase 2)."""

    async def dependency(request: Request, db: AsyncSession = Depends(get_db)) -> User:
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise UnauthorizedError("Authentication is required.")

        payload = decode_access_token(token)
        if payload is None:
            raise UnauthorizedError("Your session has expired. Please sign in again.")

        granted = set(payload.get("perms", []))
        if not set(permissions).issubset(granted):
            raise ForbiddenError("You do not have permission to perform this action.")

        user = await UserRepository(db).get_by_public_id(payload["sub"])
        if user is None or user.status != "active":
            raise UnauthorizedError("Your session is no longer valid.")
        return user

    return dependency


def verify_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise ForbiddenError("CSRF token is missing or invalid.")
