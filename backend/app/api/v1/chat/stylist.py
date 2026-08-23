"""POST /api/v1/chat/stylist/* (chat_spec.md §7.1, §5.1). Auth is `get_optional_user` — guest OK,
matching spec §5's "Auth: optional (guest OK)" row.

The Stylist's pipeline (app/agents/stylist.py) isn't a free-form tool loop like Insights/Support,
so there are no `tool_start`/`tool_end` moments to report — but its intro prose IS now genuinely
token-streamed (app/agents/stylist.py's `_write_intro`), so this route relays real `token` events
live, the same as the other two agents, just without any tool-progress events mixed in.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_optional_user
from app.core.errors import LlmUpstreamError
from app.core.rate_limit import rate_limit
from app.models.auth import User
from app.schemas.chat import ChatMessageIn, ChatResponseOut, ChatSessionCreateIn, ChatSessionOut, ToolTraceOut
from app.services.chat.stylist_service import StylistChatService

router = APIRouter(prefix="/chat/stylist", tags=["chat-stylist"])


@router.post("/session", response_model=ChatSessionOut)
async def create_session(
    payload: ChatSessionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ChatSessionOut:
    chat_session = await StylistChatService(db).create_session(user)
    return ChatSessionOut.model_validate(chat_session)


def _envelope(chat_session_public_id: str, message, blocks: list[dict], relaxation_applied: list[str]) -> ChatResponseOut:
    return ChatResponseOut(
        message_id=message.public_id,
        session_id=chat_session_public_id,
        agent="stylist",
        content=message.content,
        blocks=blocks,
        tool_trace=[ToolTraceOut(**t) for t in (message.tool_trace or [])],
        relaxation_applied=relaxation_applied,
        created_at=message.created_at,
    )


@router.post("")
async def send_message(
    payload: ChatMessageIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    _rl: None = Depends(rate_limit("chat_stylist", limit=20, window_seconds=60)),
):
    service = StylistChatService(db)
    chat_session = (
        await service.get_session(user, payload.session_id)
        if payload.session_id
        else await service.create_session(user)
    )

    if not payload.stream:
        message, blocks, relaxation_applied = await service.send_message(user, chat_session, payload.message)
        return _envelope(chat_session.public_id, message, blocks, relaxation_applied)

    return StreamingResponse(_sse_stream(service, user, chat_session, payload.message), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _sse_stream(service: StylistChatService, user: User | None, chat_session, message: str):
    queue: asyncio.Queue = asyncio.Queue()
    outcome: dict = {}

    async def on_event(event: dict) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            outcome["message"], outcome["blocks"], outcome["relaxation_applied"] = await service.send_message(
                user, chat_session, message, on_event=on_event
            )
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = exc
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    while True:
        event = await queue.get()
        if event is None:
            break
        if event["type"] == "token":
            yield _sse("token", {"delta": event["delta"]})
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
            "relaxation_applied": outcome["relaxation_applied"],
        },
    )
