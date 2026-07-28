from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories.cms import BannerRepository, CmsPageRepository
from app.schemas.cms import BannerOut, CmsPageOut


class CmsService:
    """Public-facing reads only — draft pages and inactive/out-of-window banners never surface
    here regardless of what's asked for; admin CRUD lives in `services.admin.cms_service`."""

    def __init__(self, session: AsyncSession):
        self.pages = CmsPageRepository(session)
        self.banners = BannerRepository(session)

    async def get_published_page(self, slug: str) -> CmsPageOut:
        page = await self.pages.get_published_by_slug(slug)
        if page is None:
            raise NotFoundError("This page was not found.")
        return CmsPageOut.model_validate(page)

    async def list_banners(self, placement: str) -> list[BannerOut]:
        banners = await self.banners.list_active_by_placement(placement)
        return [BannerOut.model_validate(b) for b in banners]
