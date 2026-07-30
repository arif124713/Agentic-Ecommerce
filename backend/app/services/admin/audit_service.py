from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditLogRepository
from app.schemas.admin_audit import AuditLogOut


class AdminAuditService:
    def __init__(self, session: AsyncSession):
        self.audit = AuditLogRepository(session)

    async def list_logs(
        self, *, resource_type: str | None, actor_user_id: int | None, page: int, per_page: int
    ) -> tuple[list[AuditLogOut], int]:
        logs, total = await self.audit.list_all(
            resource_type=resource_type, actor_user_id=actor_user_id, page=page, per_page=per_page
        )
        return [AuditLogOut.model_validate(log) for log in logs], total
