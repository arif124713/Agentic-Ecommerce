import datetime

from sqlalchemy import CHAR, JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    """chat_spec.md §10's `chat_sessions`. Addressed by `public_id` (ULID) in the API — the
    frontend's `session_id` — never the internal `id`, same enumeration-resistance convention as
    `SupportTicket.public_id`. `user_id` is nullable because the Stylist Agent allows guest
    sessions (spec §5, open question #2); Support and Insights sessions always carry a user_id,
    enforced at the service layer rather than here since the column is shared across all three
    agents."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent: Mapped[str] = mapped_column(String(20), nullable=False)
    last_active_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("agent IN ('stylist','support','insights')", name="ck_chat_sessions_agent"),
        Index("ix_chat_sessions_user_agent", "user_id", "agent", "last_active_at"),
        Index("ix_chat_sessions_expires", "expires_at"),
    )


class ChatMessage(Base):
    """chat_spec.md §10's `chat_messages` / §6's response envelope. `blocks` and `tool_trace` are
    stored verbatim as JSON (same pattern as `orders.shipping_address_json`) so the envelope
    returned by `GET /chat/session/{id}/history` is a direct read, not a reassembly. `content` is
    the model-authored prose only — product facts, prices, order data live in `blocks`, never in
    `content` (spec §9.3's construction guarantee)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(CHAR(26), unique=True, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    blocks: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    tool_trace: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','tool','system')", name="ck_chat_messages_role"),
        Index("ix_chat_messages_session", "session_id", "created_at"),
    )


class ToolCallLog(Base):
    """chat_spec.md §10's `tool_call_log` — one row per MCP `tools/call` made while producing a
    given assistant message, across all three agents. `arguments` is the exact JSON sent to the
    MCP server, useful for reproducing a bad tool call without needing the LLM transcript."""

    __tablename__ = "tool_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    server: Mapped[str] = mapped_column(String(40), nullable=False)
    tool: Mapped[str] = mapped_column(String(80), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_tool_call_log_message", "message_id"),
        Index("ix_tool_call_log_tool", "tool", "created_at"),
    )


class AdminAuditLog(Base):
    """chat_spec.md §4.4's hard constraint: "All [analytics-mcp] calls are audit-logged with
    admin_user_id, tool name, arguments, latency, row count." Deliberately separate from the
    existing generic `audit_logs` table (`app/models/audit.py`), which records admin *mutations*
    with a before/after diff — analytics-mcp is read-only by design (spec §5.3.4), so this table's
    shape is a call record, not a diff."""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    tool: Mapped[str] = mapped_column(String(80), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False)
    rows_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_admin_audit_log_actor", "admin_user_id", "created_at"),
        Index("ix_admin_audit_log_tool", "tool", "created_at"),
    )
