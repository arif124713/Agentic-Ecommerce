"""MCP Client Pool (chat_spec.md §3.1) — the bridge's connection to the four MCP servers deployed
on Railway (chat_implementation_plan.md §5).

Opens a fresh streamable-http connection per operation rather than holding sessions open across
requests. Spec's diagram implies "connect once at startup"; this bridge instead runs on Vercel's
Fluid Compute, where a process is reused but never guaranteed persistent across invocations —
holding a long-lived MCP session across requests would mean silently-dead connections on cold
starts, which is worse than the small per-call connection overhead. Tool SCHEMAS (from
`list_tools`) ARE cached in-process after first fetch, since a server's tool set doesn't change at
runtime; only the actual `call_tool` round-trips reconnect every time.
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool

from app.core.config import get_settings

_tool_cache: dict[str, list[Tool]] = {}


def _server_urls() -> dict[str, str]:
    settings = get_settings()
    return {
        "catalog": settings.catalog_mcp_url,
        "weather": settings.weather_mcp_url,
        "support": settings.support_mcp_url,
        "analytics": settings.analytics_mcp_url,
    }


@asynccontextmanager
async def _session(server: str):
    url = _server_urls()[server]
    settings = get_settings()
    headers = {"X-MCP-Internal-Secret": settings.mcp_internal_secret} if settings.mcp_internal_secret else None
    async with streamablehttp_client(url, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_tools(server: str, *, force_refresh: bool = False) -> list[Tool]:
    if not force_refresh and server in _tool_cache:
        return _tool_cache[server]
    async with _session(server) as session:
        result = await session.list_tools()
        _tool_cache[server] = result.tools
        return result.tools


@dataclass
class ToolCallResult:
    ok: bool
    data: Any
    error: str | None
    latency_ms: int


def _extract_text(result) -> str | None:
    for block in result.content:
        if hasattr(block, "text"):
            return block.text
    return None


def _parse_content(result) -> Any:
    text = _extract_text(result)
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def call_tool(server: str, tool_name: str, arguments: dict) -> ToolCallResult:
    start = time.monotonic()
    try:
        async with _session(server) as session:
            result = await session.call_tool(tool_name, arguments)
    except Exception as exc:  # noqa: BLE001 — genuinely any transport/protocol failure becomes a tool-level error, not a crash
        return ToolCallResult(ok=False, data=None, error=str(exc), latency_ms=int((time.monotonic() - start) * 1000))

    latency_ms = int((time.monotonic() - start) * 1000)
    if result.isError:
        return ToolCallResult(ok=False, data=None, error=_extract_text(result) or "tool error", latency_ms=latency_ms)

    data = result.structuredContent if result.structuredContent is not None else _parse_content(result)
    return ToolCallResult(ok=True, data=data, error=None, latency_ms=latency_ms)


def to_openai_function(tool: Tool, *, hidden_params: frozenset[str] = frozenset()) -> dict:
    """Converts an MCP Tool descriptor into an OpenAI-style function-calling schema, stripping any
    params in `hidden_params` — e.g. support-mcp's `user_id`, which is a real MCP tool argument
    (app/mcp/support.py) but must never be visible to or settable by the model (see that module's
    docstring for the full reasoning). Injected server-side by the caller instead."""
    schema = tool.inputSchema or {}
    properties = {k: v for k, v in (schema.get("properties") or {}).items() if k not in hidden_params}
    required = [r for r in (schema.get("required") or []) if r not in hidden_params]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }
