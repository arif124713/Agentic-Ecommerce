"""Orchestrates one Stylist Agent turn (chat_spec.md §5.1). Guest sessions are allowed (spec §5:
"Auth: optional (guest OK)") — `user` is `User | None` throughout, unlike Insights (admin-only)
and Support (login required). No `user_id` injection is needed for catalog-mcp/weather-mcp calls
— they're public read-only tools with no ownership to scope."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.agents.stylist import run_stylist_turn
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.chat import ChatMessage, ChatSession, ToolCallLog


class StylistChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user: User | None) -> ChatSession:
        settings = get_settings()
        now = utcnow()
        chat_session = ChatSession(
            public_id=str(ULID()),
            user_id=user.id if user else None,
            agent="stylist",
            last_active_at=now,
            expires_at=now + datetime.timedelta(hours=settings.session_ttl_hours),
        )
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, user: User | None, session_public_id: str) -> ChatSession:
        stmt = select(ChatSession).where(ChatSession.public_id == session_public_id, ChatSession.agent == "stylist")
        if user:
            stmt = stmt.where((ChatSession.user_id == user.id) | (ChatSession.user_id.is_(None)))
        else:
            stmt = stmt.where(ChatSession.user_id.is_(None))
        chat_session = (await self.session.execute(stmt)).scalar_one_or_none()
        if chat_session is None:
            raise NotFoundError("This chat session doesn't exist.")
        return chat_session

    async def _history_messages(self, chat_session: ChatSession) -> list[dict]:
        """Real conversation history, same shape and same source Insights/Support use
        (app/services/chat/{insights,support}_service.py) — this used to only build a flattened
        text summary fed to slot extraction, which meant the actual reply-writing calls
        (_write_intro/_write_reasons) had zero memory of anything said earlier in the session.
        Capped at 6 rather than the full max_context_messages: Stylist's generation calls already
        carry a sizeable JSON context blob (climate/weather/palette/products) on top of this."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id, ChatMessage.role.in_(("user", "assistant")))
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def send_message(
        self, user: User | None, chat_session: ChatSession, message: str, *, on_event=None
    ) -> tuple[ChatMessage, list[dict], list[str]]:
        history = await self._history_messages(chat_session)

        now = utcnow()
        self.session.add(
            ChatMessage(public_id=str(ULID()), session_id=chat_session.id, role="user", content=message, created_at=now)
        )

        result = await run_stylist_turn(message, history=history, on_event=on_event)

        assistant_message = ChatMessage(
            public_id=str(ULID()),
            session_id=chat_session.id,
            role="assistant",
            content=result["content"],
            blocks=result["blocks"],
            tool_trace=result["tool_trace"],
            created_at=utcnow(),
        )
        self.session.add(assistant_message)
        await self.session.flush()

        for trace in result["tool_trace"]:
            self.session.add(
                ToolCallLog(
                    message_id=assistant_message.id,
                    server=trace["server"],
                    tool=trace["tool"],
                    arguments={},  # the pipeline's own inputs, not model-authored — not worth duplicating here
                    ok=trace["ok"],
                    error=trace["error"],
                    rows_returned=trace["returned"],
                    latency_ms=trace["ms"],
                    created_at=utcnow(),
                )
            )

        chat_session.last_active_at = utcnow()
        await self.session.commit()
        await self.session.refresh(assistant_message)
        return assistant_message, result["blocks"], result["relaxation_applied"]
