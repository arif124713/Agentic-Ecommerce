from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.admin_audit import AuditLogOut
from app.services.admin.audit_service import AdminAuditService

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("system:audit_log:read")),
    resource_type: str | None = Query(default=None),
    actor_user_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    items, _total = await AdminAuditService(db).list_logs(
        resource_type=resource_type, actor_user_id=actor_user_id, page=page, per_page=per_page
    )
    return items
