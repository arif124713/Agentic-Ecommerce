"""Insights Agent (chat_spec.md §5.3) — the first of the three chat agents built, per spec's own
M3 recommendation: smallest tool surface, strictest boundary (analytics-mcp only, admin-gated),
so it proves the tool-allowlist/isolation pattern before the more complex Stylist/Support agents.
"""

from __future__ import annotations

from app.agents.runtime import AgentConfig

SYSTEM_PROMPT = """You are the business insights assistant for {store_name}. You are talking to
the owner or a senior manager. Assume no technical background.

- Answer with numbers from tools. Never estimate, never extrapolate, never fill a gap from general
  knowledge about retail.
- Always include a comparison: previous period, same period last week, or same period last year.
  Pick the most meaningful one and say which it is.
- Round in prose, stay exact in tables. Format currency as BDT with lakh/crore phrasing where
  natural.
- Point at the decision. If something needs reordering, promoting, or investigating, say so in one
  clause.
- Maximum five sentences of prose. Put detail in the structured block — never write a markdown
  table or restate every row yourself; the block already renders as a real sortable table with
  CSV export, so repeating it in prose is pure duplication. Your prose should name the ONE or TWO
  rows that actually matter and why, not summarize the whole table.
- If the tools can't answer it, say what you'd need and what you can offer instead. Do not
  approximate.
- You are read-only. You cannot change prices, stock, or orders. If asked, say where in the admin
  panel to do it.
- No individual customer names, emails, or addresses — you don't have access and would not share
  them if you did."""


def build_config(*, store_name: str = "BlackCart") -> AgentConfig:
    from app.core.config import get_settings

    settings = get_settings()
    return AgentConfig(
        name="insights",
        system_prompt=SYSTEM_PROMPT.format(store_name=store_name),
        servers=["analytics"],
        temperature=settings.insights_temperature,
        max_tool_iterations=settings.insights_max_tool_iterations,
    )


# tool name -> (block type, key in the tool's own JSON result holding the row list)
_TABLE_TOOLS = {
    "get_low_stock_products": ("products",),
    "get_top_products": ("products",),
    "get_category_performance": ("categories",),
    "get_sales_trend": ("buckets",),
}


def build_blocks(tool_results: list[dict]) -> list[dict]:
    """Turns the LAST successful analytics-mcp result into spec §6's `metric_summary`/
    `data_table` blocks — the one the model's final answer is actually about, not every call made
    along the way. Product facts / numbers here are copied verbatim from the tool result, never
    reconstructed from the model's prose (spec §9.3's construction guarantee)."""
    successful = [r for r in tool_results if not (isinstance(r["result"], dict) and "error" in r["result"])]
    if not successful:
        return []
    last = successful[-1]
    tool, data = last["tool"], last["result"]

    if tool in _TABLE_TOOLS and isinstance(data, dict):
        (rows_key,) = _TABLE_TOOLS[tool]
        rows = data.get(rows_key, [])
        columns = list(rows[0].keys()) if rows else []
        return [{"type": "data_table", "source_tool": tool, "columns": columns, "rows": rows}]

    return [{"type": "metric_summary", "source_tool": tool, "data": data}]
