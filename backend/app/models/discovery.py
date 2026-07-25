import datetime

from sqlalchemy import CHAR, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchQuery(Base):
    """Logged queries with result counts for zero-result analysis (spec §14.3) and to seed
    "popular past queries" in autocomplete (spec §14.4)."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_search_queries_query", "query", "created_at"),)


class Wishlist(Base):
    """One implicit wishlist per user — spec §8.3 allows named lists (plural); simplified to a
    single default list per user for this scope (documented deviation, see done.MD)."""

    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_item_product"),)


class RecentlyViewed(Base):
    __tablename__ = "recently_viewed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    viewed_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_recently_viewed_user_product"),
        Index("ix_recently_viewed_user", "user_id", "viewed_at"),
    )


class StockAlert(Base):
    """Back-in-stock notification requests (spec §8.3's stock_alerts table)."""

    __tablename__ = "stock_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False)
    notified_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("email", "variant_id", name="uq_stock_alert_email_variant"),
        Index("ix_stock_alerts_variant_pending", "variant_id", "notified_at"),
    )


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="subscribed", nullable=False)
    token: Mapped[str] = mapped_column(CHAR(43), nullable=False)
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    unsubscribed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
