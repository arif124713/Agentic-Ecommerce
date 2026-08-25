"""Stylist Agent (chat_spec.md §5.1) — deliberately NOT a free-form tool-calling loop like
Insights/Support (app/agents/runtime.py). Spec's flow diagram is a fixed pipeline: slot extraction
-> parallel climate+palette lookups -> weather -> search -> deterministic rank/diversity/
relaxation (app/agents/stylist_ranker.py) -> the model writes prose ONLY about whatever set that
pipeline already decided on. The backend decides which tools run and in what order; the model
never does, and never sees the ranking math.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from app.agents import mcp_pool
from app.agents import slot_extraction
from app.agents import stylist_ranker
from app.core.config import get_settings
from app.core.errors import LlmUpstreamError

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

StylistEventCallback = Callable[[dict], Awaitable[None]]

_RELAXATION_LADDER = ["drop_search_keywords", "drop_exclude_colors", "widen_price_max", "drop_fabrics", "drop_categories", "allow_out_of_stock"]


async def _call(server: str, tool: str, arguments: dict) -> dict | None:
    result = await mcp_pool.call_tool(server, tool, arguments)
    return result.data if result.ok else None


def _clarifying_question(missing: list[str]) -> str:
    prompts = {
        "destination": "Where are you headed, or what's the occasion you're shopping for?",
        "occasion": "What's the occasion — everyday wear, travel, something dressier?",
    }
    for slot in missing:
        if slot in prompts:
            return prompts[slot]
    return "Tell me a bit more about what you're shopping for — a destination, an occasion, or the kind of pieces you're after — and I'll pull some options."


async def _search_once(slots: dict, climate: dict | None, palette: dict | None, *, rungs_applied: set[str]) -> list[dict]:
    categories = None if "drop_categories" in rungs_applied else (climate or {}).get("suggested_categories")
    fabrics = None if "drop_fabrics" in rungs_applied else (climate or {}).get("suggested_fabrics")
    colors = (palette or {}).get("recommended") if palette else None
    exclude_colors = None if "drop_exclude_colors" in rungs_applied else ((palette or {}).get("de_emphasized") if palette else None)

    budget_max = slots.get("budget_max")
    if budget_max is not None and "widen_price_max" in rungs_applied:
        budget_max = budget_max * 1.25

    params: dict[str, object] = {
        # catalog-mcp's max — the diversity pass (stylist_ranker.select_with_diversity) can only
        # diversify across whatever this one call returns, so a bigger candidate pool matters
        # more than it would for a plain top-N search.
        "limit": 30,
        "in_stock_only": "allow_out_of_stock" not in rungs_applied,
        "skin_tone_context": slots.get("skin_depth") is not None,
    }
    search_keywords = slots.get("search_keywords")
    if search_keywords and "drop_search_keywords" not in rungs_applied:
        params["q"] = " ".join(search_keywords)
    if categories:
        params["categories"] = categories
    if colors:
        params["colors"] = colors
    if exclude_colors:
        params["exclude_colors"] = exclude_colors
    if fabrics:
        params["fabrics"] = fabrics
    if slots.get("gender"):
        params["gender"] = slots["gender"]
    if budget_max is not None:
        params["price_max"] = budget_max

    result = await _call("catalog", "search_products", params)
    return (result or {}).get("products", [])


async def _search_with_relaxation(slots: dict, climate: dict | None, palette: dict | None) -> tuple[list[dict], list[str]]:
    rungs_applied: set[str] = set()
    products = await _search_once(slots, climate, palette, rungs_applied=rungs_applied)
    applied_log: list[str] = []

    for rung in _RELAXATION_LADDER:
        if len(products) >= 5:
            break
        rungs_applied.add(rung)
        applied_log.append(rung)
        products = await _search_once(slots, climate, palette, rungs_applied=rungs_applied)

    return products, applied_log


_STYLIST_PERSONA = """You are the Stylist for {store_name} — a real fashion stylist doing your job,
not a weather reporter who happens to link products. A stylist reasons across ALL of what's given,
never just the temperature:
- the destination's actual VISUAL CHARACTER (what it looks like, what a photo there looks like —
  use it, this is what makes an outfit feel chosen for THIS place instead of generic "travel wear")
- the destination's STYLE NOTES (what's culturally normal and what reads as put-together there —
  respect these, don't override them with your own assumptions)
- the weather, only as one input among several, not the whole story
- the user's skin-tone palette, when given — the highest-weighted factor in which products were
  even selected, so when it's present it deserves real attention in your reasoning, not a footnote
- the occasion, when given

If several of these are present, weave them together into one coherent story — don't list them
as separate bullet points. If some are missing (no skin tone given, no strong style notes for a
generic query), reason fully from whatever IS given rather than padding with filler.

You may be given prior turns from this same conversation before the current request. Use them for
continuity — don't re-introduce a destination or re-explain a palette you already covered, and if
this message is a refinement ("something cheaper", "more casual") build on what you already
recommended rather than starting over. If nothing prior is relevant, ignore it."""

_INTRO_SYSTEM_PROMPT = (
    _STYLIST_PERSONA
    + """

Write ONLY the 2-3 sentence intro that sets the scene for the picks that follow — plain prose, no
JSON, no markdown, no product names or prices (those render separately from real data). Warm,
specific, brief, no filler, no hype, no emoji spam. Never comment on the user's appearance beyond
the color-matching question they asked, and always frame color choices as what will look striking,
never as fixing or improving anything."""
)

_REASONS_SYSTEM_PROMPT = (
    _STYLIST_PERSONA
    + """

You'll be given the same context plus a final, already-chosen list of products (you do not choose
or reorder them — just explain them). For each, write ONE short clause explaining why THAT item
fits THIS destination/occasion/palette specifically — reference its actual color/fabric and
something real about the destination (its look, its norms), not a generic reason that could apply
anywhere. Respond with ONLY this JSON shape: {"<product_id>": "reason", ...}. Never state a price,
stock level, size, or product name in the reason text itself."""
)


def _stylist_context(
    *, message: str, slots: dict, climate: dict | None, weather: dict | None, palette: dict | None
) -> dict:
    return {
        "latest_message": message,
        "destination": (climate or {}).get("destination"),
        "climate": (climate or {}).get("climate"),
        "visual_character": (climate or {}).get("visual_character"),
        "style_notes": (climate or {}).get("style_notes"),
        "weather": weather if (weather or {}).get("available") else {"available": False},
        "palette_recommended": (palette or {}).get("recommended"),
        "palette_rationale": (palette or {}).get("rationale"),
        "occasion": slots.get("occasion"),
    }


async def _write_intro(
    *, message: str, history: list[dict], slots: dict, climate: dict | None, weather: dict | None,
    palette: dict | None, on_event: StylistEventCallback | None,
) -> str:
    """Streams the intro live — this is the only part of a Stylist turn the user watches arrive
    token-by-token, since the per-product reasons attach to cards that only render once the whole
    turn is done anyway (see _write_reasons, a separate small non-streamed call).

    `history` (real prior turns, not just the slot-extractor's flattened summary — see
    stylist_service.py's _history_messages) is spliced in BEFORE the structured context blob so
    the model actually remembers what it already told this user this session, not just whatever
    slots got carried forward mechanically."""
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)

    context = _stylist_context(message=message, slots=slots, climate=climate, weather=weather, palette=palette)
    try:
        stream = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=cast(
                "list[ChatCompletionMessageParam]",
                [
                    {"role": "system", "content": _INTRO_SYSTEM_PROMPT.replace("{store_name}", "BlackCart")},
                    *history,
                    {"role": "user", "content": json.dumps(context)},
                ],
            ),
            temperature=settings.stylist_temperature,
            stream=True,
        )
        parts: list[str] = []
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                if on_event:
                    await on_event({"type": "token", "delta": delta})
        return "".join(parts)
    except Exception as exc:  # noqa: BLE001
        raise LlmUpstreamError(f"DeepSeek request failed: {exc}") from exc


async def _write_reasons(
    *, message: str, history: list[dict], slots: dict, climate: dict | None, weather: dict | None,
    palette: dict | None, products: list[dict],
) -> dict:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)

    context = _stylist_context(message=message, slots=slots, climate=climate, weather=weather, palette=palette)
    context["products"] = [
        {"product_id": p["product_id"], "title": p["title"], "color": p.get("color"), "fabric": p.get("fabric")}
        for p in products
    ]
    try:
        response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=cast(
                "list[ChatCompletionMessageParam]",
                [
                    {"role": "system", "content": _REASONS_SYSTEM_PROMPT.replace("{store_name}", "BlackCart")},
                    *history,
                    {"role": "user", "content": json.dumps(context)},
                ],
            ),
            temperature=settings.stylist_temperature,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001
        raise LlmUpstreamError(f"DeepSeek request failed: {exc}") from exc

    try:
        return json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {}


def _build_blocks(*, slots: dict, climate: dict | None, weather: dict | None, palette: dict | None, products: list[dict], reasons: dict) -> list[dict]:
    chips = []
    if climate and climate.get("destination"):
        chips.append({"label": climate["destination"], "icon": "map-pin"})
    if weather and weather.get("available"):
        c = weather["current"]
        chips.append({"label": f"{c['temp_c']}°C · {weather['derived']['humidity_band']}", "icon": "sun"})
        if weather["derived"]["rain_risk"] in ("high", "very-high"):
            chips.append({"label": f"{weather['daily'][0]['precip_prob']}% rain", "icon": "cloud-rain"})
    if palette:
        chips.append({"label": f"{slots.get('skin_depth', '').replace('-', ' ').title()} tone palette", "icon": "palette"})

    blocks = []
    if chips:
        blocks.append({"type": "context_chips", "items": chips})

    grid_products = []
    for p in products:
        card = dict(p)  # verbatim tool data — the model's `reasons` text is the ONLY model-authored field added
        card["reason"] = reasons.get(p["product_id"], "")
        card["actions"] = ["add_to_cart", "view_details"] if p.get("in_stock") else ["notify_me"]
        if not p.get("in_stock"):
            card["out_of_stock"] = True
        grid_products.append(card)
    blocks.append({"type": "product_grid", "products": grid_products})

    followups = []
    if slots.get("budget_max") is None:
        followups.append("Show me under ৳2000")
    if slots.get("gender") is None:
        followups.extend(["Men's picks", "Women's picks"])
    if slots.get("occasion") is None:
        followups.append("What about evenings?")
    if followups:
        blocks.append({"type": "followup_chips", "items": followups[:3]})

    return blocks


async def run_stylist_turn(
    message: str, *, history: list[dict] | None = None, on_event: StylistEventCallback | None = None
) -> dict:
    """Returns {"content", "blocks", "tool_trace", "relaxation_applied"} — same envelope shape
    the other two agents' services build from AgentTurnResult, but assembled by this fixed
    pipeline instead of app/agents/runtime.py's free-form loop.

    `history` (real prior chat_messages rows, oldest-first — see stylist_service.py) is the actual
    short-term memory: the slot extractor gets a flattened text version of it (cheap enough for a
    small classification-style call), and the two prose-writing calls get the real messages
    spliced into their own request, not just whatever slots got mechanically carried forward."""
    tool_trace: list[dict] = []
    history = history or []

    def _trace(server: str, tool: str, ms: int, ok: bool, returned: int | None = None) -> None:
        tool_trace.append({"server": server, "tool": tool, "ms": ms, "ok": ok, "error": None, "returned": returned})

    import time

    prior_context = "\n".join(f"{m['role']}: {m['content']}" for m in history) or None
    slots = await slot_extraction.extract_slots(message, prior_context)

    if slots["missing_critical"]:
        question = _clarifying_question(slots["missing_critical"])
        if on_event:
            await on_event({"type": "token", "delta": question})
        return {
            "content": question,
            "blocks": [],
            "tool_trace": [],
            "relaxation_applied": [],
        }

    climate: dict | None = None
    palette: dict | None = None

    async def _get_climate():
        nonlocal climate
        if not slots.get("destination"):
            return
        start = time.monotonic()
        climate = await _call("catalog", "get_climate_profile", {"destination": slots["destination"]})
        _trace("catalog", "get_climate_profile", int((time.monotonic() - start) * 1000), climate is not None)

    async def _get_palette():
        nonlocal palette
        if not slots.get("skin_depth"):
            return
        start = time.monotonic()
        palette = await _call("catalog", "get_color_palette", {"depth": slots["skin_depth"], "undertone": slots.get("undertone", "unknown")})
        _trace("catalog", "get_color_palette", int((time.monotonic() - start) * 1000), palette is not None)

    await asyncio.gather(_get_climate(), _get_palette())

    weather: dict | None = None
    if climate and climate.get("lat") is not None:
        start = time.monotonic()
        weather = await _call("weather", "get_weather_forecast", {"lat": climate["lat"], "lon": climate["lon"]})
        _trace("weather", "get_weather_forecast", int((time.monotonic() - start) * 1000), bool(weather and weather.get("available")))

    start = time.monotonic()
    products, relaxation_applied = await _search_with_relaxation(slots, climate, palette)
    _trace("catalog", "search_products", int((time.monotonic() - start) * 1000), True, returned=len(products))

    if not products:
        shortfall_content = (
            "I couldn't find anything matching that combination right now — the catalog's a "
            "bit thin here. Want me to open a ticket so we can flag it, or try a broader "
            "search?"
        )
        if on_event:
            await on_event({"type": "token", "delta": shortfall_content})
        return {
            "content": shortfall_content,
            "blocks": [],
            "tool_trace": tool_trace,
            "relaxation_applied": relaxation_applied,
        }

    scored = stylist_ranker.score_products(
        products,
        recommended_colors=(palette or {}).get("recommended", []),
        de_emphasized_colors=(palette or {}).get("de_emphasized", []),
        suggested_fabrics=(climate or {}).get("suggested_fabrics", []),
        avoid_fabrics=(climate or {}).get("avoid_fabrics", []),
        occasion=slots.get("occasion"),
        budget_max=slots.get("budget_max"),
    )
    selected = stylist_ranker.select_with_diversity(scored, target=max(6, min(8, len(products))))

    if len(selected) < 5:
        shortfall_note = (
            f" I found {len(selected)} — the catalog's thin for this exact combination, but here's what's there:"
        )
    else:
        shortfall_note = ""

    intro, reasons = await asyncio.gather(
        _write_intro(message=message, history=history, slots=slots, climate=climate, weather=weather, palette=palette, on_event=on_event),
        _write_reasons(message=message, history=history, slots=slots, climate=climate, weather=weather, palette=palette, products=selected),
    )
    if shortfall_note and on_event:
        await on_event({"type": "token", "delta": shortfall_note})
    content = intro + shortfall_note
    blocks = _build_blocks(slots=slots, climate=climate, weather=weather, palette=palette, products=selected, reasons=reasons)

    return {"content": content, "blocks": blocks, "tool_trace": tool_trace, "relaxation_applied": relaxation_applied}
