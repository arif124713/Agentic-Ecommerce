from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemIn(BaseModel):
    variant_id: int
    quantity: int = Field(default=1, ge=1, le=10)


class CartItemQuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=10)


class ApplyCouponIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class CartItemVariantOut(BaseModel):
    sku: str
    size: str | None
    color: str | None
    color_hex: str | None


class CartItemProductOut(BaseModel):
    slug: str
    title: str
    brand: str
    thumbnail_url: str | None


class CartItemOut(BaseModel):
    id: int
    variant_id: int
    variant: CartItemVariantOut
    product: CartItemProductOut
    quantity: int
    unit_price: Decimal
    unit_price_snapshot: Decimal
    price_changed: bool
    available: int
    is_active: bool
    line_total: Decimal


class CartTotals(BaseModel):
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    estimated_total: Decimal


class CartOut(BaseModel):
    public_id: str
    currency: str
    items: list[CartItemOut]
    coupon_code: str | None
    coupon_error: str | None
    totals: CartTotals
