from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.cms import BannerOut, CmsPageOut
from app.services.cms_service import CmsService

router = APIRouter(tags=["cms"])


@router.get("/pages/{slug}", response_model=CmsPageOut)
async def get_page(slug: str, db: AsyncSession = Depends(get_db)):
    return await CmsService(db).get_published_page(slug)


@router.get("/banners", response_model=list[BannerOut])
async def list_banners(placement: str = Query(...), db: AsyncSession = Depends(get_db)):
    return await CmsService(db).list_banners(placement)
