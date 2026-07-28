from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utcnow
from app.models.cms import Banner, CmsPage


class CmsPageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_published_by_slug(self, slug: str) -> CmsPage | None:
        stmt = select(CmsPage).where(
            CmsPage.slug == slug, CmsPage.status == "published", CmsPage.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, *, page: int, per_page: int) -> tuple[list[CmsPage], int]:
        # No global soft-delete filter exists in this codebase (spec §8.1 asks for one; each
        # query site filters `deleted_at.is_(None)` explicitly instead) — admin list intentionally
        # includes soft-deleted pages, same as the admin product list, so there's a way back.
        stmt = select(CmsPage)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(CmsPage.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def get_by_id(self, page_id: int) -> CmsPage | None:
        stmt = select(CmsPage).where(CmsPage.id == page_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> CmsPage | None:
        stmt = select(CmsPage).where(CmsPage.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, page: CmsPage) -> None:
        self.session.add(page)


class BannerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active_by_placement(self, placement: str) -> list[Banner]:
        now = utcnow()
        stmt = (
            select(Banner)
            .where(
                Banner.placement == placement,
                Banner.is_active.is_(True),
                Banner.deleted_at.is_(None),
                or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
                or_(Banner.ends_at.is_(None), Banner.ends_at >= now),
            )
            .order_by(Banner.sort_order)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all(self, *, page: int, per_page: int) -> tuple[list[Banner], int]:
        stmt = select(Banner)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Banner.placement, Banner.sort_order).offset((page - 1) * per_page).limit(per_page)
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def get_by_id(self, banner_id: int) -> Banner | None:
        stmt = select(Banner).where(Banner.id == banner_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, banner: Banner) -> None:
        self.session.add(banner)
