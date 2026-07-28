from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.timeutil import utcnow
from app.models.cms import Banner, CmsPage
from app.repositories.cms import BannerRepository, CmsPageRepository
from app.schemas.admin_cms import BannerAdminOut, BannerWriteIn, CmsPageAdminOut, CmsPageWriteIn


class AdminCmsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pages = CmsPageRepository(session)
        self.banners = BannerRepository(session)

    # --- CMS pages ---

    async def list_pages(self, *, page: int, per_page: int) -> tuple[list[CmsPageAdminOut], int]:
        pages, total = await self.pages.list_all(page=page, per_page=per_page)
        return [self._page_out(p) for p in pages], total

    async def get_page(self, page_id: int) -> CmsPageAdminOut:
        page = await self.pages.get_by_id(page_id)
        if page is None:
            raise NotFoundError("Page was not found.")
        return self._page_out(page)

    async def create_page(self, payload: CmsPageWriteIn) -> CmsPageAdminOut:
        if await self.pages.get_by_slug(payload.slug) is not None:
            raise ConflictError(f"A page with slug '{payload.slug}' already exists.")

        data = payload.model_dump()
        published_at = utcnow() if data["status"] == "published" else None
        page = CmsPage(**data, published_at=published_at)
        self.pages.add(page)
        await self.session.commit()
        return self._page_out(page)

    async def update_page(self, page_id: int, payload: CmsPageWriteIn) -> CmsPageAdminOut:
        page = await self.pages.get_by_id(page_id)
        if page is None:
            raise NotFoundError("Page was not found.")

        existing = await self.pages.get_by_slug(payload.slug)
        if existing is not None and existing.id != page_id:
            raise ConflictError(f"A page with slug '{payload.slug}' already exists.")

        was_published = page.status == "published"
        for field, value in payload.model_dump().items():
            setattr(page, field, value)
        if page.status == "published" and not was_published:
            page.published_at = utcnow()
        await self.session.commit()
        return self._page_out(page)

    async def delete_page(self, page_id: int) -> CmsPageAdminOut:
        page = await self.pages.get_by_id(page_id)
        if page is None:
            raise NotFoundError("Page was not found.")
        page.deleted_at = utcnow()
        await self.session.commit()
        return self._page_out(page)

    async def restore_page(self, page_id: int) -> CmsPageAdminOut:
        page = await self.pages.get_by_id(page_id)
        if page is None:
            raise NotFoundError("Page was not found.")
        page.deleted_at = None
        await self.session.commit()
        return self._page_out(page)

    @staticmethod
    def _page_out(page: CmsPage) -> CmsPageAdminOut:
        return CmsPageAdminOut(
            id=page.id,
            slug=page.slug,
            title=page.title,
            body=page.body,
            status=page.status,
            seo_title=page.seo_title,
            seo_description=page.seo_description,
            published_at=page.published_at,
            is_deleted=page.deleted_at is not None,
        )

    # --- Banners ---

    async def list_banners(self, *, page: int, per_page: int) -> tuple[list[BannerAdminOut], int]:
        banners, total = await self.banners.list_all(page=page, per_page=per_page)
        return [BannerAdminOut.model_validate(b) for b in banners], total

    async def get_banner(self, banner_id: int) -> BannerAdminOut:
        banner = await self.banners.get_by_id(banner_id)
        if banner is None:
            raise NotFoundError("Banner was not found.")
        return BannerAdminOut.model_validate(banner)

    async def create_banner(self, payload: BannerWriteIn) -> BannerAdminOut:
        banner = Banner(**payload.model_dump())
        self.banners.add(banner)
        await self.session.commit()
        return BannerAdminOut.model_validate(banner)

    async def update_banner(self, banner_id: int, payload: BannerWriteIn) -> BannerAdminOut:
        banner = await self.banners.get_by_id(banner_id)
        if banner is None:
            raise NotFoundError("Banner was not found.")
        for field, value in payload.model_dump().items():
            setattr(banner, field, value)
        await self.session.commit()
        return BannerAdminOut.model_validate(banner)

    async def delete_banner(self, banner_id: int) -> BannerAdminOut:
        banner = await self.banners.get_by_id(banner_id)
        if banner is None:
            raise NotFoundError("Banner was not found.")
        banner.deleted_at = utcnow()
        banner.is_active = False
        await self.session.commit()
        return BannerAdminOut.model_validate(banner)
