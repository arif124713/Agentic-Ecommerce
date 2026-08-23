"""Orchestrates one Support Agent turn (chat_spec.md §5.2): the intent gate runs FIRST and, on a
BLOCKED_INTENTS hit, the main agent (and therefore support-mcp) is never even touched — a canned
refusal is persisted and returned directly. This mirrors spec §3.1's isolation guarantee at the
intent layer too: it's not that the model is instructed not to call tools on a blocked message,
it's that `run_agent_turn` is simply never invoked for one.
"""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.agents import intent_gate
from app.agents import support as support_agent
from app.agents.runtime import AgentEventCallback, AgentTurnResult, run_agent_turn
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.chat import ChatMessage, ChatSession, ToolCallLog


class SupportChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user: User) -> ChatSession:
        settings = get_settings()
        now = utcnow()
        chat_session = ChatSession(
            public_id=str(ULID()),
            user_id=user.id,
            agent="support",
            last_active_at=now,
            expires_at=now + datetime.timedelta(hours=settings.session_ttl_hours),
        )
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, user: User, session_public_id: str) -> ChatSession:
        stmt = select(ChatSession).where(
            ChatSession.public_id == session_public_id,
            ChatSession.user_id == user.id,
            ChatSession.agent == "support",
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

    async def _blocked_count(self, chat_session: ChatSession) -> int:
        """Counts prior refusal turns THIS session, via the `blocks[0].type == "refusal"` marker
        set below — spec §5.2.2's 3-strikes escalation rule needs this per-session count, and
        there's no dedicated column for it (a marker in the existing JSON column is enough)."""
        stmt = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.session_id == chat_session.id,
            ChatMessage.role == "assistant",
            func.json_unquote(func.json_extract(ChatMessage.blocks, "$[0].type")) == "refusal",
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _persist_refusal(self, chat_session: ChatSession, user_message: str, intent: str, refusal_text: str) -> ChatMessage:
        now = utcnow()
        self.session.add(
            ChatMessage(public_id=str(ULID()), session_id=chat_session.id, role="user", content=user_message, created_at=now)
        )
        assistant_message = ChatMessage(
            public_id=str(ULID()),
            session_id=chat_session.id,
            role="assistant",
            content=refusal_text,
            blocks=[{"type": "refusal", "intent": intent}],
            tool_trace=[],
            created_at=utcnow(),
        )
        self.session.add(assistant_message)
        chat_session.last_active_at = utcnow()
        await self.session.commit()
        await self.session.refresh(assistant_message)
        return assistant_message

    async def send_message(
        self, user: User, chat_session: ChatSession, message: str, *, on_event: AgentEventCallback | None = None
    ) -> tuple[ChatMessage, list[dict]]:
        intent = await intent_gate.classify_intent(message)

        if intent in intent_gate.BLOCKED_INTENTS:
            blocked_count = await self._blocked_count(chat_session) + 1
            escalation = intent_gate.escalation_response(blocked_count)
            refusal_text = escalation or intent_gate.CANNED_REFUSALS[intent]
            assistant_message = await self._persist_refusal(chat_session, message, intent, refusal_text)
            # Never reached run_agent_turn, so no "token" events fired for it above — the SSE
            # route only relays events, it never reads message.content directly, so a refusal
            # must still emit one to actually reach the client.
            if on_event:
                await on_event({"type": "token", "delta": refusal_text})
            return assistant_message, []

        sensitive = intent == intent_gate.SENSITIVE_CONTEXT
        history = await self._history_messages(chat_session)
        config = support_agent.build_config(user_id=user.id, sensitive=sensitive)
        messages = [{"role": "system", "content": config.system_prompt}, *history, {"role": "user", "content": message}]

        now = utcnow()
        self.session.add(
            ChatMessage(public_id=str(ULID()), session_id=chat_session.id, role="user", content=message, created_at=now)
        )

        result: AgentTurnResult = await run_agent_turn(config, messages, on_event=on_event)
        blocks = support_agent.build_blocks(result.tool_results)

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
        await self.session.flush()

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

        chat_session.last_active_at = utcnow()
        await self.session.commit()
        await self.session.refresh(assistant_message)
        return assistant_message, blocks
