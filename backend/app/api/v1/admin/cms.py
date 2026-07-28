from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.admin_cms import BannerAdminOut, BannerWriteIn, CmsPageAdminOut, CmsPageWriteIn
from app.services.admin.cms_service import AdminCmsService

router = APIRouter(prefix="/admin/cms", tags=["admin-cms"])


@router.get("/pages", response_model=list[CmsPageAdminOut])
async def list_pages(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("cms:page:write")),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await AdminCmsService(db).list_pages(page=page, per_page=per_page)
    return items


@router.get("/pages/{page_id}", response_model=CmsPageAdminOut)
async def get_page(
    page_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).get_page(page_id)


@router.post("/pages", response_model=CmsPageAdminOut, status_code=201)
async def create_page(
    payload: CmsPageWriteIn, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).create_page(payload)


@router.patch("/pages/{page_id}", response_model=CmsPageAdminOut)
async def update_page(
    page_id: int,
    payload: CmsPageWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("cms:page:write")),
):
    return await AdminCmsService(db).update_page(page_id, payload)


@router.delete("/pages/{page_id}", response_model=CmsPageAdminOut)
async def delete_page(
    page_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).delete_page(page_id)


@router.post("/pages/{page_id}/restore", response_model=CmsPageAdminOut)
async def restore_page(
    page_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).restore_page(page_id)


@router.get("/banners", response_model=list[BannerAdminOut])
async def list_banners(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("cms:page:write")),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await AdminCmsService(db).list_banners(page=page, per_page=per_page)
    return items


@router.get("/banners/{banner_id}", response_model=BannerAdminOut)
async def get_banner(
    banner_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).get_banner(banner_id)


@router.post("/banners", response_model=BannerAdminOut, status_code=201)
async def create_banner(
    payload: BannerWriteIn, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).create_banner(payload)


@router.patch("/banners/{banner_id}", response_model=BannerAdminOut)
async def update_banner(
    banner_id: int,
    payload: BannerWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("cms:page:write")),
):
    return await AdminCmsService(db).update_banner(banner_id, payload)


@router.delete("/banners/{banner_id}", response_model=BannerAdminOut)
async def delete_banner(
    banner_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require("cms:page:write"))
):
    return await AdminCmsService(db).delete_banner(banner_id)
