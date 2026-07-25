import datetime
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_EXCLUDED_PATHS = {"/healthz", "/readyz", "/version", "/openapi.json", "/docs", "/redoc"}


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """Wraps successful JSON payloads in the standard {"data", "meta"} envelope (spec §10.2).

    Error responses are already enveloped by the exception handlers in app.core.errors,
    and collection endpoints that already return {"data", "meta", "facets"} are passed
    through with meta.request_id/timestamp filled in.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.url.path in _EXCLUDED_PATHS or response.status_code >= 400:
            return response

        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            payload = json.loads(body)
        except ValueError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        request_id = getattr(request.state, "request_id", None)
        timestamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

        if isinstance(payload, dict) and "data" in payload and "meta" in payload:
            payload["meta"]["request_id"] = request_id
            payload["meta"]["timestamp"] = timestamp
            enveloped = payload
        else:
            enveloped = {"data": payload, "meta": {"request_id": request_id, "timestamp": timestamp}}

        new_body = json.dumps(enveloped).encode("utf-8")
        new_response = Response(content=new_body, status_code=response.status_code, media_type="application/json")
        # `dict(response.headers)` would collapse repeated headers (e.g. multiple Set-Cookie
        # for access/refresh/csrf) down to one, silently dropping cookies. Copy the raw header
        # list instead, which preserves duplicates, and only swap out content-length/-type.
        # Mutate in place (not `new_response.raw_headers = [...]`) — the Response's MutableHeaders
        # wrapper holds a reference to this exact list object, so rebinding the attribute would
        # desync `.headers` (used by downstream middleware) from what actually gets sent.
        preserved = [(k, v) for k, v in response.raw_headers if k not in (b"content-length", b"content-type")]
        new_response.raw_headers.clear()
        new_response.raw_headers.extend(preserved)
        new_response.raw_headers.append((b"content-type", b"application/json"))
        new_response.raw_headers.append((b"content-length", str(len(new_body)).encode()))
        return new_response
