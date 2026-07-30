from pydantic import BaseModel


class PaymentWebhookEventIn(BaseModel):
    """Body of a signed webhook delivery to POST /payments/webhook/simulator (spec §12.5)."""

    event_id: str
    event_type: str
    order_id: int
    transaction_id: str
    status: str
    failure_code: str | None = None
    failure_message: str | None = None
