from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.core.audit import AuditContext, get_audit_context
from app.models.auth import User
from app.schemas.admin_feature_flag import FeatureFlagOut, FeatureFlagUpdateIn, FeatureFlagWriteIn
from app.services.admin.feature_flag_service import AdminFeatureFlagService

router = APIRouter(prefix="/admin/feature-flags", tags=["admin-feature-flags"])


@router.get("", response_model=list[FeatureFlagOut])
async def list_feature_flags(
    db: AsyncSession = Depends(get_db), _user: User = Depends(require("system:feature_flag:write"))
):
    return await AdminFeatureFlagService(db).list_flags()


@router.get("/{key}", response_model=FeatureFlagOut)
async def get_feature_flag(
    key: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require("system:feature_flag:write"))
):
    return await AdminFeatureFlagService(db).get_flag(key)


@router.post("", response_model=FeatureFlagOut, status_code=201)
async def create_feature_flag(
    payload: FeatureFlagWriteIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("system:feature_flag:write")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminFeatureFlagService(db).create_flag(payload, ctx)


@router.patch("/{key}", response_model=FeatureFlagOut)
async def update_feature_flag(
    key: str,
    payload: FeatureFlagUpdateIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("system:feature_flag:write")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminFeatureFlagService(db).update_flag(key, payload, ctx)
