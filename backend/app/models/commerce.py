import datetime
import decimal

from sqlalchemy import (
    CHAR,
    DECIMAL,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Address(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    division: Mapped[str] = mapped_column(String(80), nullable=False)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    street_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    street_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default_shipping: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default_billing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_addresses_user", "user_id", "is_default_shipping"),)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_token: Mapped[str | None] = mapped_column(CHAR(64), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), default="INR", nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    converted_order_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_carts_user", "user_id", "status"),)


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    added_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    variant: Mapped["ProductVariant"] = relationship()  # noqa: F821

    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_item_variant"),
        CheckConstraint("quantity BETWEEN 1 AND 10", name="ck_cart_item_quantity"),
    )


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    max_discount_amount: Mapped[decimal.Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    min_order_amount: Mapped[decimal.Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    usage_limit_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    starts_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    discount_amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    redeemed_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_coupon_redemptions_coupon_user", "coupon_id", "user_id"),
        UniqueConstraint("order_id", "coupon_id", name="uq_redemption_order_coupon"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(24), nullable=False)
    fulfilment_status: Mapped[str] = mapped_column(String(24), default="unfulfilled", nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    subtotal: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    shipping_fee: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    tax_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    grand_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    paid_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    refunded_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    shipping_address_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    billing_address_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(24), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    promised_delivery_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    promised_delivery_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(CHAR(64), unique=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_status", "status", "created_at"),
        CheckConstraint("grand_total >= 0", name="ck_orders_grand_total_nonneg"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_snapshot: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_snapshot: Mapped[str | None] = mapped_column(String(24), nullable=True)
    color_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    unit_mrp: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    tax_amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), default=0, nullable=False)
    line_total: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_order_status_history_order", "order_id", "created_at"),)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="simulated", nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    card_last4: Mapped[str | None] = mapped_column(CHAR(4), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    authorised_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    captured_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    failed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_payments_order", "order_id"),)


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    # Webhook delivery id (spec §12.5 step 2: "deduplicates on event_id") — unique so a replayed
    # or duplicate-delivered webhook can never be applied twice.
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    carrier: Mapped[str] = mapped_column(String(80), default="BlackCart Simulated Logistics", nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    shipped_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    estimated_delivery_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    events: Mapped[list["ShipmentEvent"]] = relationship(back_populates="shipment", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_shipments_order", "order_id"),)


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    shipment: Mapped["Shipment"] = relationship(back_populates="events")

    __table_args__ = (Index("ix_shipment_events_shipment", "shipment_id", "occurred_at"),)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(nullable=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_refunds_order", "order_id"),)
