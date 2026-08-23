"""Runs tests/guardrails/cases.yaml against the REAL intent classifier (app/agents/intent_gate.py)
— a live DeepSeek call per case, deliberately not mocked, since the whole point of this corpus
(spec §12.2) is catching classifier drift a mock could never reveal. Skipped when no
DEEPSEEK_API_KEY is configured (CI/other devs without a key shouldn't get a hard failure here) —
every OTHER test in this suite runs key-free, this file is the sole exception.
"""

from pathlib import Path

import pytest
import yaml

from app.agents import intent_gate
from app.core.config import get_settings

_CASES = yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(
    not get_settings().deepseek_api_key, reason="DEEPSEEK_API_KEY not configured"
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _CASES, ids=[c["category"] + ":" + c["input"][:30] for c in _CASES])
async def test_guardrail_case(case: dict) -> None:
    intent = await intent_gate.classify_intent(case["input"])
    expect = case["expect"]

    if expect == "block":
        assert intent in intent_gate.BLOCKED_INTENTS, f"expected BLOCK, classifier said {intent!r} for: {case['input']!r}"
    elif expect == "sensitive":
        assert intent == intent_gate.SENSITIVE_CONTEXT, f"expected sensitive_context, got {intent!r} for: {case['input']!r}"
    else:
        assert intent in intent_gate.ALLOWED_INTENTS, f"expected ALLOW, classifier said {intent!r} for: {case['input']!r}"
