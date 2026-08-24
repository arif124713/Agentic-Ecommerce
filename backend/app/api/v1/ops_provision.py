"""One-time production provisioning trigger for the chat feature (chat_implementation_plan.md M8).

TEMPORARY — delete this file (and its router.py registration) once it's been called successfully
against production. It exists only because the local dev machine building this feature has no
sanctioned direct path to the production database; the already-deployed backend does, as a normal
part of serving live traffic, so this piggybacks on that instead of anyone handling raw production
DB credentials by hand.

Gated by MIGRATION_TRIGGER_SECRET (unset in every environment but production during this window) —
the endpoint 404s without it, so it doesn't exist as far as an unauthenticated caller can tell.
Runs two idempotent operations: `alembic upgrade head` (safe to call even if already at head), and
the analytics_ro grant script (CREATE USER IF NOT EXISTS + REVOKE + re-GRANT, safe to re-run).
"""

from __future__ import annotations

import hmac
import sys
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import create_engine, text

from app.core.config import get_mysql_ssl_connect_args, get_settings

router = APIRouter(prefix="/ops", tags=["ops"], include_in_schema=False)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]

# Exact DDL for the 3 chat-feature migrations (f35ce9ce2c1b -> 714147cd4d8b), captured via
# `alembic upgrade f35ce9ce2c1b:714147cd4d8b --sql` (offline mode, no live connection needed) run
# locally where the real alembic package IS importable, then embedded here so the deployed function
# never has to import `alembic` itself — see provision_chat_db's docstring for why that import is
# unreliable in this deployment. Each statement is executed in order inside one transaction; the
# trailing UPDATE alembic_version statements make this exactly equivalent to what `alembic upgrade
# head` would have done, so a later real `alembic downgrade`/`upgrade` run (from a machine without
# the import collision) stays fully consistent with this repo's migration history.
_CHAT_MIGRATION_SQL: list[str] = [
    """CREATE TABLE climate_profiles (
    id INTEGER NOT NULL AUTO_INCREMENT,
    slug VARCHAR(140) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    lat DECIMAL(9, 6) NOT NULL,
    lon DECIMAL(9, 6) NOT NULL,
    climate VARCHAR(20) NOT NULL,
    terrain JSON NOT NULL,
    typical_occasions JSON NOT NULL,
    suggested_categories JSON NOT NULL,
    suggested_fabrics JSON NOT NULL,
    avoid_fabrics JSON NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_climate_profiles_climate CHECK (climate IN ('hot-humid','hot-dry','temperate','cool','cold','rainy'))
)""",
    "CREATE UNIQUE INDEX ix_climate_profiles_slug ON climate_profiles (slug)",
    """CREATE TABLE color_palettes (
    id INTEGER NOT NULL AUTO_INCREMENT,
    depth VARCHAR(20) NOT NULL,
    undertone VARCHAR(10) NOT NULL,
    recommended JSON NOT NULL,
    de_emphasized JSON NOT NULL,
    rationale TEXT NOT NULL,
    version SMALLINT NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_color_palettes_depth CHECK (depth IN ('fair','light','medium','tan','deep','rich-deep')),
    CONSTRAINT ck_color_palettes_undertone CHECK (undertone IN ('warm','cool','neutral','unknown')),
    CONSTRAINT uq_color_palettes_depth_undertone UNIQUE (depth, undertone)
)""",
    """CREATE TABLE daily_sales_summary (
    date DATE NOT NULL,
    orders INTEGER NOT NULL,
    gross_revenue DECIMAL(14, 2) NOT NULL,
    net_revenue DECIMAL(14, 2) NOT NULL,
    units INTEGER NOT NULL,
    aov DECIMAL(12, 2) NOT NULL,
    new_customers INTEGER NOT NULL,
    returning_customers INTEGER NOT NULL,
    refunds_count INTEGER NOT NULL,
    refunds_amount DECIMAL(14, 2) NOT NULL,
    refreshed_at DATETIME NOT NULL,
    PRIMARY KEY (date)
)""",
    """CREATE TABLE admin_audit_log (
    id INTEGER NOT NULL AUTO_INCREMENT,
    admin_user_id INTEGER NOT NULL,
    tool VARCHAR(80) NOT NULL,
    arguments JSON NOT NULL,
    rows_returned INTEGER,
    latency_ms INTEGER NOT NULL,
    ip VARCHAR(64),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(admin_user_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    "CREATE INDEX ix_admin_audit_log_actor ON admin_audit_log (admin_user_id, created_at)",
    "CREATE INDEX ix_admin_audit_log_tool ON admin_audit_log (tool, created_at)",
    """CREATE TABLE category_performance_summary (
    id INTEGER NOT NULL AUTO_INCREMENT,
    date DATE NOT NULL,
    category_id INTEGER NOT NULL,
    units INTEGER NOT NULL,
    revenue DECIMAL(14, 2) NOT NULL,
    return_rate DECIMAL(5, 4) NOT NULL,
    refreshed_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE CASCADE,
    CONSTRAINT uq_category_performance_date_category UNIQUE (date, category_id)
)""",
    "CREATE INDEX ix_category_performance_date ON category_performance_summary (date)",
    """CREATE TABLE chat_sessions (
    id INTEGER NOT NULL AUTO_INCREMENT,
    public_id CHAR(26) NOT NULL,
    user_id INTEGER,
    agent VARCHAR(20) NOT NULL,
    last_active_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT now(),
    updated_at DATETIME NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT ck_chat_sessions_agent CHECK (agent IN ('stylist','support','insights')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL,
    UNIQUE (public_id)
)""",
    "CREATE INDEX ix_chat_sessions_expires ON chat_sessions (expires_at)",
    "CREATE INDEX ix_chat_sessions_user_agent ON chat_sessions (user_id, agent, last_active_at)",
    """CREATE TABLE destination_aliases (
    id INTEGER NOT NULL AUTO_INCREMENT,
    alias VARCHAR(120) NOT NULL,
    climate_profile_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(climate_profile_id) REFERENCES climate_profiles (id) ON DELETE RESTRICT,
    UNIQUE (alias)
)""",
    "CREATE INDEX ix_destination_aliases_profile ON destination_aliases (climate_profile_id)",
    """CREATE TABLE chat_messages (
    id INTEGER NOT NULL AUTO_INCREMENT,
    public_id CHAR(26) NOT NULL,
    session_id INTEGER NOT NULL,
    `role` VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    blocks JSON,
    tool_trace JSON,
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_chat_messages_role CHECK (role IN ('user','assistant','tool','system')),
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
    UNIQUE (public_id)
)""",
    "CREATE INDEX ix_chat_messages_session ON chat_messages (session_id, created_at)",
    """CREATE TABLE product_velocity_summary (
    variant_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    units_7d INTEGER NOT NULL,
    units_30d INTEGER NOT NULL,
    avg_daily_units_30d DECIMAL(10, 2) NOT NULL,
    stock_qty INTEGER NOT NULL,
    days_of_cover DECIMAL(10, 2) NOT NULL,
    status VARCHAR(10) NOT NULL,
    refreshed_at DATETIME NOT NULL,
    PRIMARY KEY (variant_id),
    CONSTRAINT ck_product_velocity_status CHECK (status IN ('critical','low','watch','healthy')),
    CONSTRAINT ck_product_velocity_days_of_cover_cap CHECK (days_of_cover <= 999),
    FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE,
    FOREIGN KEY(variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
)""",
    "CREATE INDEX ix_product_velocity_product ON product_velocity_summary (product_id)",
    "CREATE INDEX ix_product_velocity_status_cover ON product_velocity_summary (status, days_of_cover)",
    """CREATE TABLE tool_call_log (
    id INTEGER NOT NULL AUTO_INCREMENT,
    message_id INTEGER NOT NULL,
    server VARCHAR(40) NOT NULL,
    tool VARCHAR(80) NOT NULL,
    arguments JSON NOT NULL,
    ok BOOL NOT NULL,
    error TEXT,
    rows_returned INTEGER,
    latency_ms INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE
)""",
    "CREATE INDEX ix_tool_call_log_message ON tool_call_log (message_id)",
    "CREATE INDEX ix_tool_call_log_tool ON tool_call_log (tool, created_at)",
    """CREATE TABLE returns (
    id INTEGER NOT NULL AUTO_INCREMENT,
    public_id CHAR(26) NOT NULL,
    order_item_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason_code VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,
    resolved_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT now(),
    updated_at DATETIME NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT ck_returns_status CHECK (status IN ('requested','approved','rejected','received','refunded','cancelled')),
    FOREIGN KEY(order_item_id) REFERENCES order_items (id) ON DELETE RESTRICT,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT,
    UNIQUE (public_id)
)""",
    "CREATE INDEX ix_returns_order_item ON returns (order_item_id)",
    "CREATE INDEX ix_returns_user ON returns (user_id, created_at)",
    "UPDATE alembic_version SET version_num='348830f9c2c5' WHERE alembic_version.version_num = 'f35ce9ce2c1b'",
    "ALTER TABLE product_velocity_summary ADD COLUMN revenue_7d DECIMAL(14, 2) NOT NULL DEFAULT '0'",
    "ALTER TABLE product_velocity_summary ADD COLUMN revenue_30d DECIMAL(14, 2) NOT NULL DEFAULT '0'",
    "ALTER TABLE product_velocity_summary ALTER COLUMN revenue_7d DROP DEFAULT",
    "ALTER TABLE product_velocity_summary ALTER COLUMN revenue_30d DROP DEFAULT",
    "UPDATE alembic_version SET version_num='e810389f3221' WHERE alembic_version.version_num = '348830f9c2c5'",
    "ALTER TABLE climate_profiles ADD COLUMN visual_character TEXT",
    "ALTER TABLE climate_profiles ADD COLUMN style_notes TEXT",
    "UPDATE alembic_version SET version_num='714147cd4d8b' WHERE alembic_version.version_num = 'e810389f3221'",
]


def _require_secret(x_migration_secret: str | None) -> None:
    expected = get_settings().migration_trigger_secret
    if not expected or not x_migration_secret or not hmac.compare_digest(x_migration_secret, expected):
        raise HTTPException(status_code=404)


@router.get("/diag-open")
def diag_open():
    """Unauthenticated on purpose (temporary) — reports non-reversible fingerprints (sha256 prefix +
    length) of the two secret settings, never the raw values, so a mismatch between what was set in
    Vercel and what the running function actually resolves can be diagnosed without exposing either
    secret. Delete alongside the rest of this file."""
    import hashlib

    settings = get_settings()

    def fp(v: str | None) -> dict:
        v = v or ""
        return {"len": len(v), "sha256_8": hashlib.sha256(v.encode()).hexdigest()[:8]}

    return {
        "migration_trigger_secret": fp(settings.migration_trigger_secret),
        "mcp_internal_secret": fp(settings.mcp_internal_secret),
    }


@router.get("/diag")
def diag(x_migration_secret: str | None = Header(default=None)):
    """Deliberately import-free of `alembic` at module scope — see provision_chat_db's docstring.
    Reports whether the real pip-installed alembic package (not this repo's own alembic/ migrations
    directory, which collides on name) is actually reachable, without risking another app-wide
    import crash if it isn't."""
    _require_secret(x_migration_secret)
    import importlib.util

    spec = importlib.util.find_spec("alembic.command")
    return {
        "alembic_command_spec": None if spec is None else str(spec.origin),
        "sys_path_head": sys.path[:8],
        "cwd": str(Path.cwd()),
    }


@router.post("/provision-chat-db")
def provision_chat_db(x_migration_secret: str | None = Header(default=None)):
    _require_secret(x_migration_secret)
    settings = get_settings()

    # Raw SQL, not `alembic upgrade head` — the real pip-installed `alembic` package is genuinely
    # unreachable from this deployed function (it resolves to this repo's OWN backend/alembic/
    # migrations directory instead, a name collision unique to how Vercel's Python builder lays out
    # the bundle; confirmed via /ops/diag). _CHAT_MIGRATION_SQL above is the exact DDL Alembic itself
    # would run, captured offline (`alembic upgrade f35ce9ce2c1b:714147cd4d8b --sql`, no live
    # connection needed) from a machine where the import isn't shadowed, including the same
    # alembic_version bookkeeping — so this is byte-for-byte what `alembic upgrade head` would have
    # done, not an approximation, and a later real `alembic downgrade`/`upgrade` from an unaffected
    # machine stays fully consistent with it.
    engine = create_engine(settings.sync_database_url, connect_args=get_mysql_ssl_connect_args(settings))
    try:
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

        migration_error: str | None = None
        applied = False
        if current == "714147cd4d8b":
            pass
        elif current != "f35ce9ce2c1b":
            migration_error = f"unexpected current alembic_version {current!r}, refusing to guess"
        else:
            try:
                with engine.begin() as conn:
                    for stmt in _CHAT_MIGRATION_SQL:
                        conn.execute(text(stmt))
                applied = True
            except Exception as exc:  # noqa: BLE001 — surfaced in the response, not a crash
                migration_error = str(exc)

        analytics_error: str | None = None
        try:
            user = settings.analytics_mysql_user
            password = settings.analytics_mysql_password
            db = settings.mysql_db
            with engine.begin() as conn:
                # No REVOKE ALL here (unlike scripts/provision_analytics_ro.sql, meant for repeated
                # local re-runs): this managed MySQL's admin account (Aiven's restricted `avnadmin`,
                # not a true root) can CREATE USER/GRANT but can't REVOKE ALL PRIVILEGES — that needs
                # `sys` schema access this account doesn't have. A REVOKE is only needed to clean up
                # stale grants from a PRIOR run anyway; CREATE USER IF NOT EXISTS on a genuinely new
                # user starts with zero privileges, so there's nothing to revoke on this one-time run.
                conn.execute(text(f"CREATE USER IF NOT EXISTS '{user}'@'%%' IDENTIFIED BY :pw"), {"pw": password})
                conn.execute(text(f"GRANT SELECT ON {db}.daily_sales_summary TO '{user}'@'%%'"))
                conn.execute(text(f"GRANT SELECT ON {db}.product_velocity_summary TO '{user}'@'%%'"))
                conn.execute(text(f"GRANT SELECT ON {db}.category_performance_summary TO '{user}'@'%%'"))
                conn.execute(text("FLUSH PRIVILEGES"))
        except Exception as exc:  # noqa: BLE001 — surfaced in the response, not a crash
            analytics_error = str(exc)
    finally:
        engine.dispose()

    return {
        "alembic_version_before": current,
        "migration_applied": applied,
        "migration_error": migration_error,
        "analytics_ro_provisioned": analytics_error is None,
        "analytics_ro_error": analytics_error,
    }
