"""CSP violation reporting endpoint (spec §22.2's `report-uri`). Browsers POST here whenever a
page served under this API's origin violates the Content-Security-Policy header — a spike is an
early XSS signal per spec. Accepts the body as raw JSON rather than a strict Pydantic schema:
browsers use two different historical report shapes (`application/csp-report` and the newer
Reporting API's `application/reports+json`), and the only thing that matters here is capturing
whatever came in for someone to look at, not validating its shape."""

import structlog
from fastapi import APIRouter, Request, Response

logger = structlog.get_logger("blackcart.security")

router = APIRouter(tags=["security"])


@router.post("/csp-report", status_code=204)
async def csp_report(request: Request):
    try:
        payload = await request.json()
    except ValueError:
        payload = {"raw": (await request.body()).decode("utf-8", errors="replace")}
    logger.warning("csp_violation", report=payload)
    return Response(status_code=204)
