from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.seo import router as seo_router
from app.api.v1.operational import router as operational_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.storage import MEDIA_ROOT
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.response_envelope import ResponseEnvelopeMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()
configure_logging()
logger = get_logger("blackcart.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup", env=settings.app_env)
    yield


app = FastAPI(
    title="BlackCart API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Order matters: earlier add_middleware() calls end up innermost (closest to the route), later
# calls end up outermost (closest to the wire). SecurityHeadersMiddleware must be innermost so
# its headers exist on the response object before ResponseEnvelopeMiddleware rebuilds it (that
# middleware copies raw_headers forward rather than starting fresh, but only headers already
# present on the response it receives). Request ID must be bound before anything logs or envelopes.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ResponseEnvelopeMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-MFA-Challenge"],
)

register_exception_handlers(app)

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

app.include_router(operational_router)
app.include_router(seo_router)
app.include_router(api_router, prefix=settings.api_prefix)

# spec §21.2's Prometheus metrics — request rate/latency/status per route out of the box
# (http_requests_total, http_request_duration_seconds). The rest of §21.2's business/domain
# metrics (orders_created_total, payment_attempts_total, etc.), §21.3's OpenTelemetry tracing,
# and §21.4's Grafana dashboards/alerts all need infrastructure this native setup doesn't have
# (a collector, a Grafana instance) — not attempted, documented in done.MD. /metrics itself is
# unauthenticated here, matching Prometheus's usual internal-network-only scrape model; it would
# need a network-level restriction (or basic auth) in a real deployment, which is Nginx's job.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
