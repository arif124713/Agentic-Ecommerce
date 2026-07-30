from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.core.audit import AuditContext, get_audit_context
from app.models.auth import User
from app.schemas.admin_api_key import ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut
from app.services.admin.api_key_service import AdminApiKeyService

router = APIRouter(prefix="/admin/api-keys", tags=["admin-api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    db: AsyncSession = Depends(get_db), _user: User = Depends(require("system:api_key:manage"))
):
    return await AdminApiKeyService(db).list_keys()


@router.post("", response_model=ApiKeyCreatedOut, status_code=201)
async def create_api_key(
    payload: ApiKeyCreateIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("system:api_key:manage")),
    ctx: AuditContext = Depends(get_audit_context),
):
    return await AdminApiKeyService(db).create_key(payload, ctx)


@router.delete("/{public_id}", status_code=204)
async def revoke_api_key(
    public_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("system:api_key:manage")),
    ctx: AuditContext = Depends(get_audit_context),
):
    await AdminApiKeyService(db).revoke_key(public_id, ctx)
    return Response(status_code=204)
