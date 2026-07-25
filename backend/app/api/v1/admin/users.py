from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.admin_user import AdminUserDetail, AdminUserListItem, AssignRoleIn, SuspendUserIn
from app.services.admin.user_service import AdminUserService

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=list[AdminUserListItem])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("iam:user:read")),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await AdminUserService(db).list_users(q=q, page=page, per_page=per_page)
    return items


@router.get("/{public_id}", response_model=AdminUserDetail)
async def get_user(public_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require("iam:user:read"))):
    return await AdminUserService(db).get_user(public_id)


@router.post("/{public_id}/roles", response_model=AdminUserDetail)
async def assign_role(
    public_id: str,
    payload: AssignRoleIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("iam:user:assign_role")),
):
    return await AdminUserService(db).assign_role(public_id, payload.role_code)


@router.delete("/{public_id}/roles/{role_code}", response_model=AdminUserDetail)
async def revoke_role(
    public_id: str,
    role_code: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("iam:user:assign_role")),
):
    return await AdminUserService(db).revoke_role(public_id, role_code)


@router.post("/{public_id}/suspend", response_model=AdminUserDetail)
async def suspend_user(
    public_id: str,
    payload: SuspendUserIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require("iam:user:read")),
):
    return await AdminUserService(db).suspend(public_id, actor_public_id=user.public_id, reason=payload.reason)


@router.post("/{public_id}/reactivate", response_model=AdminUserDetail)
async def reactivate_user(
    public_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require("iam:user:read"))
):
    return await AdminUserService(db).reactivate(public_id)
