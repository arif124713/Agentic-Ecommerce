import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CouponWriteIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    description: str | None = None
    discount_type: str = Field(pattern="^(percent|fixed|free_shipping)$")
    discount_value: Decimal = Decimal("0")
    max_discount_amount: Decimal | None = None
    min_order_amount: Decimal | None = None
    usage_limit_total: int | None = None
    usage_limit_per_user: int | None = None
    stackable: bool = False
    starts_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    is_active: bool = True


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: Decimal
    max_discount_amount: Decimal | None
    min_order_amount: Decimal | None
    usage_limit_total: int | None
    usage_limit_per_user: int | None
    used_count: int
    stackable: bool
    starts_at: datetime.datetime | None
    expires_at: datetime.datetime | None
    is_active: bool
