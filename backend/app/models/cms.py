import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class CmsPage(Base, TimestampMixin, SoftDeleteMixin):
    """Static content pages (spec §8.3's `cms_pages` table) — About, Terms, Privacy, FAQ, etc.
    Rendered publicly at `/pages/{slug}` (spec §17.1's route map) once `status = 'published'`;
    a draft page 404s for everyone except through the admin CRUD endpoints."""

    __tablename__ = "cms_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_cms_pages_status"),
    )


class Banner(Base, TimestampMixin, SoftDeleteMixin):
    """Merchandising banners (spec §8.3), scoped by `placement` (e.g. `home_promo`) and an
    optional active date window. `ProductRail`'s own "renders nothing if empty" convention is
    mirrored on the frontend for banner strips — an empty placement is not an error state."""

    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    placement: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    starts_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_banners_placement_active", "placement", "is_active", "sort_order"),
    )
