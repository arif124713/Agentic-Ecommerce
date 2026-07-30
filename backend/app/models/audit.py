import datetime

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """spec §22.6: every admin mutation writes a row here, before/after JSON diff included, inside
    the same transaction as the change it records — every service method that writes one calls
    `AuditLogRepository.record()` in the same unit of work as its own `session.commit()`, so an
    audited action can't succeed without its audit record landing too.

    Append-only by convention: `AuditLogRepository` deliberately has no update/delete methods (the
    practical equivalent, at the application layer, of spec's "no UPDATE/DELETE grants on the table
    for the application DB user" — this dev setup has one shared DB user for the whole app, so
    revoking grants at the database level would also block every other table that same user needs
    to write)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(50), nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_actor", "actor_user_id", "created_at"),
        Index("ix_audit_logs_created", "created_at"),
    )
