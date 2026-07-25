import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Review(Base, TimestampMixin):
    """Product reviews (spec §8.3, §9.7). Only users with a DELIVERED order item for the product
    may create one (is_verified_purchase is always true in v1 — unverified reviews are disabled
    per spec §9.7), so order_item_id is the eligibility proof, not an optional attribution field."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    moderated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("product_id", "user_id", "order_item_id", name="uq_review_product_user_item"),
        Index("ix_reviews_product_status", "product_id", "status"),
        Index("ix_reviews_status_created", "status", "created_at"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
    )
