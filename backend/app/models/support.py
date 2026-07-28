import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth import User


class SupportTicket(Base, TimestampMixin):
    """spec §8.3's `support_tickets` table. Addressed by `public_id` (ULID), never the internal
    `id`, per spec §8.1's enumeration-resistance convention — a customer's own ticket list is
    scoped by `user_id` anyway, but the id shouldn't be guessable from one ticket to the next."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    assignee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Two FKs to `users` on this table (user_id, assignee_user_id) — foreign_keys must be explicit
    # on both relationships or SQLAlchemy can't infer which column backs which (the exact
    # AmbiguousForeignKeysError documented in done.MD's Phase 2 auth-backend section, for the
    # analogous user_id/granted_by pair on user_roles).
    assignee: Mapped["User"] = relationship(foreign_keys=[assignee_user_id])
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", order_by="TicketMessage.created_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('open','pending','resolved','closed')", name="ck_support_tickets_status"),
        CheckConstraint("priority IN ('low','medium','high')", name="ck_support_tickets_priority"),
        Index("ix_support_tickets_user", "user_id", "created_at"),
        Index("ix_support_tickets_status", "status", "created_at"),
        Index("ix_support_tickets_assignee", "assignee_user_id", "status"),
    )


class TicketMessage(Base):
    """Threaded messages (spec §8.3). `author_type` distinguishes a customer's own message from a
    staff reply for rendering (left/right bubble, "Support Team" label) without a join back to
    roles. Attachments (spec §8.3) are out of scope — no file-upload pipeline exists yet in this
    project (documented gap, consistent with every other upload-shaped feature)."""

    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_type: Mapped[str] = mapped_column(String(10), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("author_type IN ('customer','staff')", name="ck_ticket_messages_author_type"),
        Index("ix_ticket_messages_ticket", "ticket_id", "created_at"),
    )
