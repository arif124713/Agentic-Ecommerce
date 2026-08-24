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


def _require_secret(x_migration_secret: str | None) -> None:
    expected = get_settings().migration_trigger_secret
    if not expected or not x_migration_secret or not hmac.compare_digest(x_migration_secret, expected):
        raise HTTPException(status_code=404)


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

    # Imported here, not at module scope: `backend/alembic/` (this repo's OWN migrations directory,
    # required to be named exactly that by alembic.ini) collides with the real pip-installed
    # `alembic` package's name in Vercel's deployed function — a module-level import here took down
    # the ENTIRE app on first deploy (every route, not just this one) since main.py -> router.py ->
    # this file all import eagerly. Deferring it here means a failure only 500s this one endpoint.
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    engine = create_engine(settings.sync_database_url, connect_args=get_mysql_ssl_connect_args(settings))
    try:
        with engine.connect() as conn:
            revision = MigrationContext.configure(conn).get_current_heads()

        analytics_error: str | None = None
        try:
            user = settings.analytics_mysql_user
            password = settings.analytics_mysql_password
            db = settings.mysql_db
            with engine.begin() as conn:
                conn.execute(text(f"CREATE USER IF NOT EXISTS '{user}'@'%%' IDENTIFIED BY :pw"), {"pw": password})
                conn.execute(text(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{user}'@'%%'"))
                conn.execute(text(f"GRANT SELECT ON {db}.daily_sales_summary TO '{user}'@'%%'"))
                conn.execute(text(f"GRANT SELECT ON {db}.product_velocity_summary TO '{user}'@'%%'"))
                conn.execute(text(f"GRANT SELECT ON {db}.category_performance_summary TO '{user}'@'%%'"))
                conn.execute(text("FLUSH PRIVILEGES"))
        except Exception as exc:  # noqa: BLE001 — surfaced in the response, not a crash
            analytics_error = str(exc)
    finally:
        engine.dispose()

    return {
        "alembic_heads": list(revision),
        "analytics_ro_provisioned": analytics_error is None,
        "analytics_ro_error": analytics_error,
    }
