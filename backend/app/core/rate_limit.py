"""Lightweight in-process rate limiting (spec §10.7/§22.1's DoS control). Spec's design is a
Redis-backed token bucket shared across every API worker; there's no Redis here (see done.MD), so
this is a plain in-memory fixed-window counter scoped to a single process — correct for this
native single-worker dev setup, but would under-count (allow more requests than the stated limit)
if this ever ran behind multiple worker processes without a shared store. A documented gap, not a
silent one — the same category of deviation as the DB-based login lockout replacing a Redis one."""

import time

from fastapi import Depends, Request

from app.api.deps import get_client_ip
from app.core.errors import RateLimitedError

_buckets: dict[str, tuple[float, int]] = {}


def _check(key: str, *, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    window_start, count = _buckets.get(key, (now, 0))
    if now - window_start >= window_seconds:
        window_start, count = now, 0

    count += 1
    _buckets[key] = (window_start, count)

    if count > limit:
        retry_after = max(1, int(window_seconds - (now - window_start)) + 1)
        raise RateLimitedError(
            f"Too many requests. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(name: str, *, limit: int, window_seconds: int):
    """Per-IP fixed-window limiter, applied as a route dependency:
    `Depends(rate_limit("register", limit=5, window_seconds=3600))`."""

    def dependency(request: Request, ip: str | None = Depends(get_client_ip)) -> None:
        _check(f"{name}:{ip or 'unknown'}", limit=limit, window_seconds=window_seconds)

    return dependency
