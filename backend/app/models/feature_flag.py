from sqlalchemy import JSON, Boolean, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FeatureFlag(Base, TimestampMixin):
    """spec §28: boolean toggle + percentage rollout + targeting rules, editable by Super Admins.
    Spec caches this in Redis with a 30s TTL; no Redis in this native setup (the same documented
    gap as every other Redis-shaped feature here), so every read is a fresh query — correct at this
    scale, would need revisiting under real traffic."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rollout_percent: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    targeting: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
