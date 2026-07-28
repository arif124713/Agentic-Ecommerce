"""Security response headers (spec §22.2). Spec puts these at the Nginx layer; there's no Nginx
in this native-Windows setup (see done.MD), so they're applied here instead as a FastAPI
middleware — same headers, same values, just a different layer emitting them.

This backend is a pure JSON API (no server-rendered HTML, `/docs` aside, which is disabled
outright in production), so the CSP is intentionally locked down harder than spec §22.2's
`default-src 'self'` template — spec's version is written for a page that runs Vite-built
`<script src="...">` tags and needs `script-src`/`style-src` allowances; this API never returns
HTML for the CSP to police, so `default-src 'none'` is the more correct policy for what this
service actually does. No nonce is generated because there is no inline script for a nonce to
authorise here."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings

settings = get_settings()

_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    f"report-uri {settings.api_prefix}/csp-report"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # /media is self-hosted product imagery meant to be <img>-embedded from the frontend's
        # own origin (localhost:5173 vs this API's 127.0.0.1:8000 — different origins even on the
        # same machine); CORP: same-origin would have the browser silently refuse to render them
        # there even though the fetch itself succeeds (found live: a real product image 200'd but
        # never painted until this was narrowed down to CORP, not a broken file or wrong URL).
        response.headers["Cross-Origin-Resource-Policy"] = (
            "cross-origin" if request.url.path.startswith("/media/") else "same-origin"
        )
        response.headers["Content-Security-Policy"] = _CSP
        if settings.is_production:
            # Only sent over HTTPS in practice, but the header itself is harmless to set
            # unconditionally elsewhere too — gated on is_production anyway so a plain-http local
            # dev session is never told by its own API to upgrade every future request to https.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        return response
