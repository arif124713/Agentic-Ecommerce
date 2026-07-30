import json

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.errors import UnauthorizedError, ValidationAppError
from app.core.payment import verify_webhook_signature
from app.core.rate_limit import rate_limit
from app.services.order_service import OrderService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/webhook/simulator",
    status_code=200,
    dependencies=[Depends(rate_limit("payment_webhook", limit=500, window_seconds=60))],
)
async def payment_webhook_simulator(request: Request, db: AsyncSession = Depends(get_db)):
    """spec §12.5: a signed webhook callback, verified independently of session cookies/CSRF —
    the HMAC signature *is* the auth for this endpoint, exactly as a real PSP webhook works."""
    body = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not verify_webhook_signature(body, signature):
        raise UnauthorizedError("Invalid or expired webhook signature.")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationAppError("Webhook body is not valid JSON.") from exc

    try:
        await OrderService(db).apply_payment_webhook_event(payload)
    except ValidationError as exc:
        raise ValidationAppError(
            "Webhook payload failed schema validation.",
            details=[{"field": ".".join(str(p) for p in e["loc"]), "issue": e["msg"]} for e in exc.errors()],
        ) from exc

    return {"status": "ok"}
