"""Rate limiting (spec §10.7/§22.1's DoS control). Spec's design is a Redis-backed counter shared
across every API worker — this now has one, via Upstash's REST API (a plain in-memory fixed-window
counter was the only option before this deployment had any Redis at all; see done.MD). Two
backends, selected by `RATE_LIMIT_BACKEND`:

- "memory" (default, used by local dev and the test suite): a plain in-process dict, correct for a
  single worker process but would under-count across multiple instances.
- "redis": Upstash REST, correct across every Vercel function instance, since the counter lives in
  one shared store rather than each instance's own memory.
"""

import time

import httpx
import structlog
from fastapi import Depends, Request

from app.api.deps import get_client_ip
from app.core.config import get_settings
from app.core.errors import RateLimitedError

logger = structlog.get_logger("blackcart.rate_limit")

_buckets: dict[str, tuple[float, int]] = {}


def _check_memory(key: str, *, limit: int, window_seconds: int) -> None:
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


async def _check_redis(key: str, *, limit: int, window_seconds: int) -> None:
    settings = get_settings()
    # INCR (atomic counter), EXPIRE ... NX (only arms the window on the first hit in it — a bare
    # EXPIRE every call would keep sliding the window forward and never let it reset), TTL (exact
    # seconds left, for a precise Retry-After rather than a fixed window_seconds guess).
    body = [["INCR", key], ["EXPIRE", key, str(window_seconds), "NX"], ["TTL", key]]
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{settings.redis_rest_url}/pipeline",
                headers={"Authorization": f"Bearer {settings.redis_rest_token}"},
                json=body,
            )
            response.raise_for_status()
            results = response.json()
        count = results[0]["result"]
        ttl = results[2]["result"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        # Fail open: a Redis/Upstash hiccup should degrade to "unlimited" for this one request,
        # not take the whole API down. Logged so a persistent outage is still visible.
        logger.warning("rate_limit.redis_unavailable", error=str(exc))
        return

    if count > limit:
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
        raise RateLimitedError(
            f"Too many requests. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(name: str, *, limit: int, window_seconds: int):
    """Per-IP fixed-window limiter, applied as a route dependency:
    `Depends(rate_limit("register", limit=5, window_seconds=3600))`."""

    async def dependency(request: Request, ip: str | None = Depends(get_client_ip)) -> None:
        key = f"{name}:{ip or 'unknown'}"
        if get_settings().rate_limit_backend == "redis":
            await _check_redis(key, limit=limit, window_seconds=window_seconds)
        else:
            _check_memory(key, limit=limit, window_seconds=window_seconds)

    return dependency
