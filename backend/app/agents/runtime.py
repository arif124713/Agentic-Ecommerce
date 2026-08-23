"""Generic tool-calling loop (chat_spec.md §3.1 steps 1-5), shared by all three chat agents. An
`AgentConfig` fixes the system prompt, which MCP servers are in scope (the isolation guarantee —
a server not in `config.servers` never appears in the DeepSeek request payload at all), and any
args injected server-side into every call to a given server (support-mcp's `user_id`).

Every DeepSeek call in this loop streams (verified live against the real API — see
chat_implementation_plan.md's streaming notes for the exact chunk shape). Content deltas and tool
calls both arrive incrementally; tool-call argument fragments are keyed by `index` and
concatenated as they arrive, the same accumulation pattern documented in the OpenAI streaming API
and confirmed to match DeepSeek's own implementation by a live test.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from openai import NOT_GIVEN, AsyncOpenAI

from app.agents import mcp_pool
from app.core.config import get_settings
from app.core.errors import LlmUpstreamError

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam


@dataclass
class ToolTraceEntry:
    server: str
    tool: str
    ms: int
    ok: bool
    error: str | None = None
    returned: int | None = None


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    servers: list[str]
    temperature: float
    max_tool_iterations: int
    # server -> {param: value}, always injected into every tool call on that server, invisible to
    # and unoverridable by the model (applied AFTER the model's own arguments).
    injected_args: dict[str, dict] = field(default_factory=dict)
    # server -> set of param names hidden from the schema DeepSeek sees for that server's tools.
    hidden_params: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass
class AgentTurnResult:
    content: str
    tool_trace: list[ToolTraceEntry]
    # raw {server, tool, arguments, result} per call — callers (e.g. insights.build_blocks) use
    # this to build the response envelope's structured blocks.
    tool_results: list[dict]


def _client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


async def _build_tools(config: AgentConfig) -> tuple[list[dict], dict[str, str]]:
    """Returns (openai tools[], {tool_name: owning_server}). A flat name->server map is enough to
    route a tool_call back to the right MCP server, since no two servers in this system define a
    tool with the same name."""
    tools: list[dict] = []
    owner: dict[str, str] = {}
    for server in config.servers:
        mcp_tools = await mcp_pool.list_tools(server)
        hidden = config.hidden_params.get(server, frozenset())
        for t in mcp_tools:
            tools.append(mcp_pool.to_openai_function(t, hidden_params=hidden))
            owner[t.name] = server
    return tools, owner


def _row_count(data: object) -> int | None:
    if isinstance(data, dict):
        for key in ("count", "orders", "products", "results", "categories", "buckets"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
    return None


AgentEventCallback = Callable[[dict], Awaitable[None]]
# Deprecated alias kept for any external import — the callback now carries token events too.
ToolEventCallback = AgentEventCallback


async def _stream_completion(
    client: AsyncOpenAI,
    *,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    temperature: float,
    on_event: AgentEventCallback | None,
) -> tuple[str, list[dict]]:
    """Streams one completion, forwarding each content delta through `on_event` as
    {"type": "token", "delta": ...} as it arrives. Returns (full_content, tool_calls) once the
    stream ends — tool_calls as plain dicts ({"id", "type": "function", "function": {"name", "arguments"}} —
    "type" matters: DeepSeek's API rejects a tool_calls entry missing it once that message is sent
    back as conversation history on the next round-trip, a real bug this shape hit and fixed),
    reassembled from per-index argument fragments exactly as DeepSeek streams them.

    `messages`/`tools` are built as plain dicts throughout this whole feature (agent configs,
    services, slot extraction, intent gate — matching the JSON these actually are, since they
    round-trip through JSON for persistence anyway), not the openai SDK's TypedDict unions. The
    casts below are that one intentional looseness at the single point it touches the SDK, not a
    suppressed real bug — verified live against the real API throughout this feature's build."""
    stream = await client.chat.completions.create(
        model=model,
        messages=cast("list[ChatCompletionMessageParam]", messages),
        tools=cast("list[ChatCompletionToolParam]", tools) if tools else NOT_GIVEN,
        tool_choice="auto" if tools else NOT_GIVEN,
        temperature=temperature,
        stream=True,
    )
    content_parts: list[str] = []
    tool_calls: dict[int, dict] = {}

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            content_parts.append(delta.content)
            if on_event:
                await on_event({"type": "token", "delta": delta.content})
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                slot = tool_calls.setdefault(
                    tc_delta.index, {"id": None, "type": "function", "function": {"name": "", "arguments": ""}}
                )
                if tc_delta.id:
                    slot["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        slot["function"]["name"] += tc_delta.function.name
                    if tc_delta.function.arguments:
                        slot["function"]["arguments"] += tc_delta.function.arguments

    ordered = [tool_calls[i] for i in sorted(tool_calls)]
    return "".join(content_parts), ordered


async def run_agent_turn(
    config: AgentConfig, messages: list[dict], *, on_event: AgentEventCallback | None = None
) -> AgentTurnResult:
    """`on_event`, if given, is awaited with one of:
    - {"type": "token", "delta": str} — a content fragment, forwarded live as DeepSeek streams it
    - {"type": "tool_start"/"tool_end", "server", "tool", ...} — around each MCP call
    """
    client = _client()
    settings = get_settings()
    tools, owner = await _build_tools(config)
    tool_trace: list[ToolTraceEntry] = []
    tool_results: list[dict] = []
    working_messages: list[dict] = list(messages)

    for _ in range(config.max_tool_iterations):
        try:
            content, tool_calls = await _stream_completion(
                client, model=settings.deepseek_model, messages=working_messages,
                tools=tools, temperature=config.temperature, on_event=on_event,
            )
        except Exception as exc:  # noqa: BLE001 — any DeepSeek-side failure is an upstream error, not a crash
            raise LlmUpstreamError(f"DeepSeek request failed: {exc}") from exc

        if not tool_calls:
            return AgentTurnResult(content=content, tool_trace=tool_trace, tool_results=tool_results)

        working_messages.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            server = owner.get(tool_name)
            if server is None:
                working_messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": json.dumps({"error": "unknown_tool"})}
                )
                continue

            try:
                arguments = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            # Server-side injection wins on any key collision — the model can't override user_id
            # even by guessing/echoing one, since this is applied after its own arguments.
            arguments.update(config.injected_args.get(server, {}))

            if on_event:
                await on_event({"type": "tool_start", "server": server, "tool": tool_name})
            result = await mcp_pool.call_tool(server, tool_name, arguments)
            if on_event:
                await on_event({"type": "tool_end", "server": server, "tool": tool_name, "ms": result.latency_ms, "ok": result.ok})
            tool_trace.append(
                ToolTraceEntry(
                    server=server, tool=tool_name, ms=result.latency_ms, ok=result.ok,
                    error=result.error, returned=_row_count(result.data),
                )
            )
            payload = result.data if result.ok else {"error": result.error}
            tool_results.append({"server": server, "tool": tool_name, "arguments": arguments, "result": payload})
            working_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(payload)})

    # Iteration budget exhausted — one final streamed call with no tools, forcing an answer from
    # what's already gathered rather than looping forever.
    try:
        content, _ = await _stream_completion(
            client, model=settings.deepseek_model, messages=working_messages,
            tools=None, temperature=config.temperature, on_event=on_event,
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmUpstreamError(f"DeepSeek request failed: {exc}") from exc
    return AgentTurnResult(content=content, tool_trace=tool_trace, tool_results=tool_results)
