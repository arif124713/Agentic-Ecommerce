import subprocess

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["operational"])


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"


_GIT_SHA = _git_sha()


@router.get("/healthz")
async def healthz():
    """Liveness — no dependency checks."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness — checks DB connectivity."""
    checks = {"database": "unknown"}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surfaced to the caller, not swallowed
        checks["database"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}


@router.get("/version")
async def version():
    return {"git_sha": _GIT_SHA}
