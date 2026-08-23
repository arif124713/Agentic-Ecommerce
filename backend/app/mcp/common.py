"""Shared plumbing for the four chat MCP servers (chat_implementation_plan.md §5). Each server is
its own Railway process/entrypoint, but all four live in this one Python package so they can import
`app.models`/`app.repositories` directly instead of duplicating query logic — see
chat_implementation_plan.md §2's reuse map for why that matters.

Deliberately NOT reusing `app.db.session.AsyncSessionLocal` for analytics-mcp: that engine is bound
to the primary `mysql_user` (full read/write), and the entire point of
`scripts/provision_analytics_ro.sql` is that analytics-mcp never holds those credentials. Its own
engine, bound to `analytics_ro`, is defined below.
"""

from __future__ import annotations

import datetime
import decimal
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_mysql_ssl_connect_args, get_settings

_settings = get_settings()

# Primary connection — catalog-mcp and support-mcp read (and, for support-mcp's initiate_return/
# create_support_ticket, write) through this. Same credentials as the main FastAPI app.
_primary_engine = create_async_engine(
    _settings.database_url,
    pool_size=5,
    pool_pre_ping=True,
    pool_recycle=_settings.database_pool_recycle_seconds,
    connect_args=get_mysql_ssl_connect_args(_settings),
)
PrimarySessionLocal = async_sessionmaker(bind=_primary_engine, autoflush=False, expire_on_commit=False)

# analytics_ro connection — SELECT only, on the three summary tables only (verified empirically,
# see chat_implementation_plan.md M1 status). analytics-mcp must use this and only this engine.
_analytics_engine = create_async_engine(
    _settings.analytics_database_url,
    pool_size=3,
    pool_pre_ping=True,
    pool_recycle=_settings.database_pool_recycle_seconds,
    connect_args=get_mysql_ssl_connect_args(_settings),
)
AnalyticsSessionLocal = async_sessionmaker(bind=_analytics_engine, autoflush=False, expire_on_commit=False)


@asynccontextmanager
async def primary_session() -> AsyncGenerator[AsyncSession, None]:
    async with PrimarySessionLocal() as session:
        yield session


@asynccontextmanager
async def analytics_session() -> AsyncGenerator[AsyncSession, None]:
    async with AnalyticsSessionLocal() as session:
        yield session


def to_jsonable(value):
    """MCP tool return values go through JSON serialization; `Decimal`/`date`/`datetime` aren't
    natively serializable. Recurses through dicts/lists/tuples so a tool can just build normal
    Python structures (spec response shapes use plain JSON numbers/strings throughout)."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


class ToolArgumentError(ValueError):
    """Raised by a tool when arguments are individually well-typed (FastMCP/Pydantic already
    enforced that) but jointly invalid — e.g. price_min > price_max. Spec §7.3's
    TOOL_ARGUMENT_INVALID is surfaced by the bridge (M3), not here; this just gives tool code one
    exception type to raise instead of a bare ValueError indistinguishable from a real bug."""
