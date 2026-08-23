"""POST /api/v1/chat/insights/* (chat_spec.md §7.1, §5.3). Deliberately insights-SPECIFIC routes
rather than the spec's generic `/chat/{agent}` — only this one agent is built (M3); a generic
route that 501s for stylist/support would just be a half-built surface, not a smaller one.

Auth reuses the SAME permission (`analytics:dashboard:read`) as the existing admin dashboard
(app/api/v1/admin/dashboard.py) rather than a new "admin role" check — this endpoint reads exactly
the same class of aggregate data, so gating it any differently would be an arbitrary distinction.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.core.errors import LlmUpstreamError
from app.core.rate_limit import rate_limit
from app.models.auth import User
from app.schemas.chat import ChatMessageIn, ChatResponseOut, ChatSessionCreateIn, ChatSessionOut, ToolTraceOut
from app.services.chat.insights_service import InsightsChatService

router = APIRouter(prefix="/chat/insights", tags=["chat-insights"])

_REQUIRE_INSIGHTS = require("analytics:dashboard:read")


@router.post("/session", response_model=ChatSessionOut)
async def create_session(
    payload: ChatSessionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_REQUIRE_INSIGHTS),
) -> ChatSessionOut:
    chat_session = await InsightsChatService(db).create_session(user)
    return ChatSessionOut.model_validate(chat_session)


def _envelope(chat_session_public_id: str, message, blocks: list[dict]) -> ChatResponseOut:
    return ChatResponseOut(
        message_id=message.public_id,
        session_id=chat_session_public_id,
        agent="insights",
        content=message.content,
        blocks=blocks,
        tool_trace=[ToolTraceOut(**t) for t in (message.tool_trace or [])],
        created_at=message.created_at,
    )


@router.post("")
async def send_message(
    payload: ChatMessageIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_REQUIRE_INSIGHTS),
    _rl: None = Depends(rate_limit("chat_insights", limit=60, window_seconds=60)),
):
    service = InsightsChatService(db)
    chat_session = (
        await service.get_session(user, payload.session_id)
        if payload.session_id
        else await service.create_session(user)
    )

    if not payload.stream:
        message, blocks = await service.send_message(user, chat_session, payload.message)
        return _envelope(chat_session.public_id, message, blocks)

    return StreamingResponse(
        _sse_stream(service, user, chat_session, payload.message), media_type="text/event-stream"
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _sse_stream(service: InsightsChatService, user: User, chat_session, message: str):
    """Content arrives as real per-token `token` events as DeepSeek streams them (see
    app/agents/runtime.py) — this generator is a thin relay, not a buffer. Blocks/done still wait
    for the full turn to finish, since they depend on the complete tool results."""
    queue: asyncio.Queue = asyncio.Queue()
    outcome: dict = {}

    async def on_event(event: dict) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            outcome["message"], outcome["blocks"] = await service.send_message(
                user, chat_session, message, on_event=on_event
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as an SSE error event below
            outcome["error"] = exc
        finally:
            await queue.put(None)  # sentinel: producer is done

    task = asyncio.create_task(run())
    while True:
        event = await queue.get()
        if event is None:
            break
        if event["type"] == "token":
            yield _sse("token", {"delta": event["delta"]})
        elif event["type"] == "tool_start":
            yield _sse("tool_start", {"server": event["server"], "tool": event["tool"]})
        elif event["type"] == "tool_end":
            yield _sse("tool_end", {"tool": event["tool"], "ms": event["ms"], "ok": event["ok"]})
    await task

    if "error" in outcome:
        exc = outcome["error"]
        code = exc.code if isinstance(exc, LlmUpstreamError) else "INTERNAL_ERROR"
        yield _sse("error", {"error": {"code": code, "message": str(exc), "retriable": True}})
        return

    assistant_message, blocks = outcome["message"], outcome["blocks"]
    for block in blocks:
        yield _sse("block", block)
    yield _sse(
        "done",
        {
            "message_id": assistant_message.public_id,
            "session_id": chat_session.public_id,
            "tool_trace": assistant_message.tool_trace or [],
        },
    )
