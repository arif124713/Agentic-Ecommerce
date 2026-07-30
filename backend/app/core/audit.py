"""spec §22.6's audit-logging context: who did it, from where, with what tooling — captured once
per request as a FastAPI dependency so every admin router just adds one parameter instead of
threading IP/user-agent/request-id through by hand at every call site."""

import dataclasses
import datetime
import decimal
from typing import Any

from fastapi import Depends, Request

from app.api.deps import get_current_user
from app.core.cookies import ACCESS_COOKIE
from app.core.security import decode_access_token
from app.models.auth import User


def to_json_safe(value: Any) -> Any:
    """Recursively converts a before/after snapshot dict into something SQLAlchemy's plain JSON
    type (no custom serializer configured — plain `json.dumps` under the hood) can actually store:
    `Decimal` (every price/mrp field) and `datetime` aren't JSON-serializable by default."""
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json_safe(v) for v in value]
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


@dataclasses.dataclass
class AuditContext:
    actor_user_id: int
    actor_role: str | None
    ip: str | None
    user_agent: str | None
    request_id: str | None


async def get_audit_context(request: Request, user: User = Depends(get_current_user)) -> AuditContext:
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    roles = payload.get("roles") if payload else None
    return AuditContext(
        actor_user_id=user.id,
        actor_role=",".join(roles) if roles else None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
