from contextlib import AsyncExitStack, asynccontextmanager

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
from app.mcp.analytics import mcp as analytics_mcp
from app.mcp.catalog import mcp as catalog_mcp
from app.mcp.support import mcp as support_mcp
from app.mcp.weather import mcp as weather_mcp

settings = get_settings()
configure_logging()
logger = get_logger("blackcart.main")

# The four chat-feature MCP servers (app/mcp/*.py), mounted as sub-apps rather than run as
# standalone Railway services (chat_implementation_plan.md §5 originally planned the latter) — this
# repo deploys as a single Vercel Python service, so co-locating them here is one deployment instead
# of five, at the cost of collapsing "separate network service" isolation down to "separate Starlette
# routes in one process." The tool-visibility boundary (AgentConfig.servers in app/agents/runtime.py)
# and the analytics_ro DB-role boundary are both unaffected either way — neither depends on process
# separation. Each is reached over real HTTP (CATALOG_MCP_URL etc., set to this same origin in
# production), matching local dev's `run_mcp_server.py` standalone-process URLs exactly — the bridge
# code (app/agents/mcp_pool.py) doesn't know or care which case it's in.
_MCP_APPS = {"catalog": catalog_mcp, "weather": weather_mcp, "support": support_mcp, "analytics": analytics_mcp}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup", env=settings.app_env)
    # Each FastMCP streamable-http ASGI app owns a StreamableHTTPSessionManager that MUST have its
    # `.run()` context active for the whole process lifetime — Starlette doesn't auto-propagate a
    # mounted sub-app's own lifespan into the parent's, so this has to be done explicitly (the
    # documented MCP SDK pattern for mounting multiple servers into one ASGI app).
    async with AsyncExitStack() as stack:
        for m in _MCP_APPS.values():
            await stack.enter_async_context(m.session_manager.run())
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

# Only meaningful for the local storage backend — a Vercel serverless function's filesystem is
# read-only outside /tmp, so both mkdir() and the StaticFiles mount (which requires its directory
# to exist at construction time) would crash the app at cold start if attempted unconditionally.
# Product images are served straight from Vercel Blob's own URLs when storage_backend is anything
# else, so there's nothing for this mount to do there.
if settings.storage_backend == "local":
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

app.include_router(operational_router)
app.include_router(seo_router)
app.include_router(api_router, prefix=settings.api_prefix)

# Mounted under /api/mcp/* so vercel.json's existing "/api(/.*)?" -> backend rewrite already covers
# them — no separate Vercel service/rewrite needed. Each FastMCP app registers its own streamable
# endpoint at "/mcp" relative to its mount point (FastMCP's default streamable_http_path), so the
# full path is e.g. /api/mcp/catalog/mcp — matching what CATALOG_MCP_URL etc. must be set to.
for _name, _mcp in _MCP_APPS.items():
    app.mount(f"/api/mcp/{_name}", _mcp.streamable_http_app())

# spec §21.2's Prometheus metrics — request rate/latency/status per route out of the box
# (http_requests_total, http_request_duration_seconds). The rest of §21.2's business/domain
# metrics (orders_created_total, payment_attempts_total, etc.), §21.3's OpenTelemetry tracing,
# and §21.4's Grafana dashboards/alerts all need infrastructure this native setup doesn't have
# (a collector, a Grafana instance) — not attempted, documented in done.MD. /metrics itself is
# unauthenticated here, matching Prometheus's usual internal-network-only scrape model; it would
# need a network-level restriction (or basic auth) in a real deployment, which is Nginx's job.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
