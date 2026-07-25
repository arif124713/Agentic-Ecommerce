import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AdminOrderListItem(BaseModel):
    order_number: str
    customer_email: str
    status: str
    payment_status: str
    currency: str
    grand_total: Decimal
    item_count: int
    created_at: datetime.datetime


class TransitionOrderIn(BaseModel):
    to_status: str
    reason: str | None = Field(default=None, max_length=255)


class RefundIn(BaseModel):
    amount: Decimal
    reason: str | None = Field(default=None, max_length=255)


class RefundOut(BaseModel):
    transaction_id: str
    amount: Decimal
    status: str
    processed_at: datetime.datetime | None
