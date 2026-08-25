"""Stylist Agent step 1 (chat_spec.md §5.1.1) — a single cheap, JSON-only DeepSeek call that pulls
structured slots out of free text. Deliberately NOT part of the tool-calling loop: this always
runs first and its output drives which tools get called next (deterministic orchestration, per
spec's flow diagram — the model doesn't decide whether to call get_climate_profile, the backend
does, based on what this extracted).
"""

from __future__ import annotations

import json

from app.core.config import get_settings

_DEPTHS = {"fair", "light", "medium", "tan", "deep", "rich-deep"}
_UNDERTONES = {"warm", "cool", "neutral", "unknown"}
_OCCASIONS = {"beach", "casual", "formal", "party", "travel", "festive", "office"}
_GENDERS = {"men", "women", "unisex"}

_SYSTEM_PROMPT = """Extract shopping-relevant slots from the user's message (and the short prior
conversation, if given) as a single JSON object. Respond with ONLY the JSON, no other text.

{
  "destination": string or null,
  "skin_depth": one of ["fair","light","medium","tan","deep","rich-deep"] or null,
  "undertone": one of ["warm","cool","neutral","unknown"] or null,
  "gender": one of ["men","women","unisex"] or null,
  "occasion": one of ["beach","casual","formal","party","travel","festive","office"] or null,
  "budget_max": number or null,
  "travel_date": string or null,
  "search_keywords": array of 0-4 short lowercase strings naming the CONCRETE garment/need behind
    the request — the actual product-search terms, distinct from the enum fields above. E.g. "i
    have a wedding to attend" -> ["wedding", "guest"]; "need something for hiking in the cold" ->
    ["hiking", "jacket"]; "job interview next week" -> ["interview", "formal", "shirt"]; a vague
    "help me shop"/"show me options" with no concrete need -> [].
  "missing_critical": array of strings (slot names still needed before ANY reasonable search is
    possible — this should almost always be empty; gender/occasion/budget are never "critical" on
    their own since search can proceed with sane defaults, only flag something if the message is
    so vague nothing can be searched at all, e.g. "help me shop" with zero other context)
}

RULES:
- skin_depth: users describe complexion in free text — "dark", "brown", "fair", "wheatish", Bangla
  words like "শ্যামলা" or "ফর্সা". Map these onto the enum using your best judgement. If you
  genuinely cannot map it confidently, use null rather than guessing — the caller skips the
  color-palette step entirely on null rather than acting on a bad guess.
- Only extract skin_depth if the user volunteered it. NEVER infer it from anything else, and
  never treat its absence as something to ask about.
- destination: keep the user's own words (e.g. "cox's bazar", "coxsbazar", "কক্সবাজার") — a
  separate lookup resolves aliases, don't normalize it yourself.
- search_keywords: this is what makes results reflect the SPECIFIC problem described instead of
  just destination/skin-tone/budget — pull real nouns/needs out of the message, don't repeat the
  destination or occasion enum values verbatim here.
- If a field wasn't mentioned this turn AND isn't in the prior context given to you, it's null
  (or [] for search_keywords), not a guess."""


async def extract_slots(message: str, prior_context: str | None = None) -> dict:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=15, max_retries=1)

    user_content = message if not prior_context else f"Prior context: {prior_context}\n\nLatest message: {message}"
    response = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user_content}],
        temperature=0,
        max_tokens=250,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}

    return {
        "destination": _clean_str(parsed.get("destination")),
        "skin_depth": parsed.get("skin_depth") if parsed.get("skin_depth") in _DEPTHS else None,
        "undertone": parsed.get("undertone") if parsed.get("undertone") in _UNDERTONES else "unknown",
        "gender": parsed.get("gender") if parsed.get("gender") in _GENDERS else None,
        "occasion": parsed.get("occasion") if parsed.get("occasion") in _OCCASIONS else None,
        "budget_max": _clean_number(parsed.get("budget_max")),
        "travel_date": _clean_str(parsed.get("travel_date")),
        "search_keywords": [s.strip() for s in (parsed.get("search_keywords") or []) if isinstance(s, str) and s.strip()][:4],
        "missing_critical": [s for s in (parsed.get("missing_critical") or []) if isinstance(s, str)],
    }


def _clean_str(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _clean_number(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
