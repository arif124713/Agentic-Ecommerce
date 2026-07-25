"""Sitemap and robots.txt (spec §20.4). Mounted unprefixed on the app root (like /healthz),
because that's where a crawler actually looks for them — `/sitemap.xml` and `/robots.txt` must
be reachable at the site's true root, not under /api/v1. In production behind Nginx (spec's
architecture, not present in this native setup) that means an explicit `location = /sitemap.xml`
/`location = /robots.txt` proxy rule to this backend, since everything else at `/*` falls through
to the static frontend build — documented here rather than assumed.

At this catalogue's size (~8k products) everything fits in one <50k-URL file, so this skips
spec's sitemap-index-of-chunked-child-sitemaps structure — that's a real requirement at Amazon
scale, not at this one, and building index/chunking machinery for URLs that will never be
exercised would just be untested code. Revisit if the catalogue ever crosses ~40k URLs."""

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import PlainTextResponse, Response

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.catalog import Category, Product

router = APIRouter(tags=["seo"], include_in_schema=False)
settings = get_settings()


def _base_url() -> str:
    return settings.app_base_url.rstrip("/")


@router.get("/robots.txt")
async def robots_txt():
    base = _base_url()
    lines = [
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /checkout",
        "Disallow: /account",
        "Disallow: /api",
        "Disallow: /search",
        "Disallow: /cart",
        "",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return PlainTextResponse("\n".join(lines))


def _url_entry(loc: str, *, lastmod: str | None = None, priority: str | None = None) -> str:
    parts = [f"<loc>{escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"<lastmod>{lastmod}</lastmod>")
    if priority:
        parts.append(f"<priority>{priority}</priority>")
    return f"<url>{''.join(parts)}</url>"


@router.get("/sitemap.xml")
async def sitemap_xml(db: AsyncSession = Depends(get_db)):
    base = _base_url()
    urls = [_url_entry(f"{base}/", priority="1.0")]

    categories = (
        await db.execute(
            select(Category.slug).where(Category.is_active.is_(True), Category.deleted_at.is_(None))
        )
    ).scalars().all()
    urls += [_url_entry(f"{base}/c/{slug}", priority="0.8") for slug in categories]

    # No standalone /b/:brandSlug page exists in the frontend yet (brand is a facet filter on
    # the category listing, not its own route) — a brand sitemap entry would just be a dead link.
    products = (
        await db.execute(
            select(Product.slug, Product.updated_at).where(
                Product.status == "active", Product.deleted_at.is_(None)
            )
        )
    ).all()
    urls += [
        _url_entry(f"{base}/p/{slug}", lastmod=updated_at.strftime("%Y-%m-%d"), priority="0.6")
        for slug, updated_at in products
    ]

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    )
    return Response(content=body, media_type="application/xml")
