import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CheckoutPreviewIn(BaseModel):
    shipping_address_id: int
    billing_address_id: int | None = None
    shipping_method: str = "standard"
    payment_method: str = Field(pattern="^(card|cod)$")


class CreateOrderIn(BaseModel):
    shipping_address_id: int
    billing_address_id: int | None = None
    shipping_method: str = "standard"
    payment_method: str = Field(pattern="^(card|cod)$")
    card_number: str | None = None
    customer_note: str | None = Field(default=None, max_length=500)
    accept_terms: bool


class CancelOrderIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class OrderLineOut(BaseModel):
    variant_id: int
    sku: str
    title: str
    brand: str | None
    image: str | None
    size: str | None
    color: str | None
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderTotals(BaseModel):
    subtotal: Decimal
    discount_total: Decimal
    shipping_fee: Decimal
    tax_total: Decimal
    grand_total: Decimal


class CheckoutPreviewOut(BaseModel):
    items: list[OrderLineOut]
    totals: OrderTotals
    promised_delivery_from: datetime.date
    promised_delivery_to: datetime.date


class PaymentOut(BaseModel):
    method: str
    status: str
    card_last4: str | None
    card_brand: str | None
    transaction_id: str
    failure_code: str | None
    failure_message: str | None


class OrderSummaryOut(BaseModel):
    order_number: str
    status: str
    payment_status: str
    currency: str
    grand_total: Decimal
    item_count: int
    thumbnail_url: str | None
    created_at: datetime.datetime


class OrderListOut(BaseModel):
    data: list[OrderSummaryOut]
    meta: dict


class OrderDetailOut(BaseModel):
    order_number: str
    status: str
    payment_status: str
    fulfilment_status: str
    currency: str
    items: list[OrderLineOut]
    totals: OrderTotals
    shipping_address: dict
    billing_address: dict
    customer_note: str | None
    payment: PaymentOut | None
    promised_delivery_from: datetime.date | None
    promised_delivery_to: datetime.date | None
    delivered_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    created_at: datetime.datetime


class ShipmentEventOut(BaseModel):
    status: str
    location: str | None
    description: str | None
    occurred_at: datetime.datetime


class TrackingOut(BaseModel):
    order_number: str
    tracking_number: str | None
    carrier: str | None
    shipment_status: str | None
    estimated_delivery_at: datetime.datetime | None
    delivered_at: datetime.datetime | None
    events: list[ShipmentEventOut]
