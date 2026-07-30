from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditContext
from app.core.timeutil import utcnow
from app.models.audit import AuditLog


class AuditLogRepository:
    """Deliberately append-only: no update/delete method exists here at all (see AuditLog's own
    docstring for why that's the practical equivalent of revoking UPDATE/DELETE grants in a
    single-DB-user dev setup)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def record(
        self,
        ctx: AuditContext,
        *,
        action: str,
        resource_type: str,
        resource_id: str | int,
        before: dict | None,
        after: dict | None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=ctx.actor_user_id,
                actor_role=ctx.actor_role,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                before_json=before,
                after_json=after,
                ip=ctx.ip,
                user_agent=ctx.user_agent,
                request_id=ctx.request_id,
                created_at=utcnow(),
            )
        )

    async def list_all(
        self, *, resource_type: str | None, actor_user_id: int | None, page: int, per_page: int
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        return list((await self.session.execute(stmt)).scalars().all()), total
