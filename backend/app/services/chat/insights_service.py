"""Orchestrates one Insights Agent turn (chat_spec.md §5.3): loads/creates the session, runs the
tool-calling loop (app/agents/runtime.py), and persists everything the spec's audit trail requires
— chat_messages, tool_call_log, AND admin_audit_log, since spec §4.4's hard constraint is that
EVERY analytics-mcp call is audit-logged with admin_user_id/tool/arguments/latency/row count, not
just recorded generically as a chat message.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.agents import insights as insights_agent
from app.agents.runtime import AgentEventCallback, AgentTurnResult, run_agent_turn
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.chat import AdminAuditLog, ChatMessage, ChatSession, ToolCallLog


class InsightsChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, admin_user: User) -> ChatSession:
        settings = get_settings()
        now = utcnow()
        chat_session = ChatSession(
            public_id=str(ULID()),
            user_id=admin_user.id,
            agent="insights",
            last_active_at=now,
            expires_at=now + datetime.timedelta(hours=settings.session_ttl_hours),
        )
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, admin_user: User, session_public_id: str) -> ChatSession:
        stmt = select(ChatSession).where(
            ChatSession.public_id == session_public_id,
            ChatSession.user_id == admin_user.id,
            ChatSession.agent == "insights",
        )
        chat_session = (await self.session.execute(stmt)).scalar_one_or_none()
        if chat_session is None:
            raise NotFoundError("This chat session doesn't exist or isn't yours.")
        return chat_session

    async def _history_messages(self, chat_session: ChatSession) -> list[dict]:
        settings = get_settings()
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id, ChatMessage.role.in_(("user", "assistant")))
            .order_by(ChatMessage.created_at.desc())
            .limit(settings.max_context_messages)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def send_message(
        self, admin_user: User, chat_session: ChatSession, message: str, *, on_event: AgentEventCallback | None = None
    ) -> tuple[ChatMessage, list[dict]]:
        history = await self._history_messages(chat_session)
        config = insights_agent.build_config()
        messages = [{"role": "system", "content": config.system_prompt}, *history, {"role": "user", "content": message}]

        now = utcnow()
        self.session.add(
            ChatMessage(public_id=str(ULID()), session_id=chat_session.id, role="user", content=message, created_at=now)
        )

        result: AgentTurnResult = await run_agent_turn(config, messages, on_event=on_event)
        blocks = insights_agent.build_blocks(result.tool_results)

        assistant_message = ChatMessage(
            public_id=str(ULID()),
            session_id=chat_session.id,
            role="assistant",
            content=result.content,
            blocks=blocks,
            tool_trace=[
                {"server": t.server, "tool": t.tool, "ms": t.ms, "ok": t.ok, "error": t.error, "returned": t.returned}
                for t in result.tool_trace
            ],
            created_at=utcnow(),
        )
        self.session.add(assistant_message)
        await self.session.flush()  # need assistant_message.id for tool_call_log FK below

        for trace, call in zip(result.tool_trace, result.tool_results, strict=True):
            self.session.add(
                ToolCallLog(
                    message_id=assistant_message.id,
                    server=trace.server,
                    tool=trace.tool,
                    arguments=call["arguments"],
                    ok=trace.ok,
                    error=trace.error,
                    rows_returned=trace.returned,
                    latency_ms=trace.ms,
                    created_at=utcnow(),
                )
            )
            # spec §4.4's hard constraint: EVERY analytics-mcp call is separately audit-logged,
            # not just recorded as part of the chat transcript.
            self.session.add(
                AdminAuditLog(
                    admin_user_id=admin_user.id,
                    tool=trace.tool,
                    arguments=call["arguments"],
                    rows_returned=trace.returned,
                    latency_ms=trace.ms,
                    created_at=utcnow(),
                )
            )

        chat_session.last_active_at = utcnow()
        await self.session.commit()
        await self.session.refresh(assistant_message)
        return assistant_message, blocks
