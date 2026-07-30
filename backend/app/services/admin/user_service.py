from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditContext
from app.core.errors import ConflictError, NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User, UserRole
from app.repositories.admin_user import AdminUserRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.auth import RefreshTokenRepository
from app.schemas.admin_user import AdminUserDetail, AdminUserListItem


class AdminUserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = AdminUserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.audit = AuditLogRepository(session)

    def _to_list_item(self, user: User) -> AdminUserListItem:
        return AdminUserListItem(
            public_id=user.public_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            status=user.status,
            roles=sorted(ur.role.code for ur in user.user_roles),
            created_at=user.created_at,
        )

    async def list_users(self, *, q: str | None, page: int, per_page: int) -> tuple[list[AdminUserListItem], int]:
        users, total = await self.users.list_users(q=q, page=page, per_page=per_page)
        return [self._to_list_item(u) for u in users], total

    async def get_user(self, public_id: str) -> AdminUserDetail:
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        base = self._to_list_item(user)
        return AdminUserDetail(
            **base.model_dump(),
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            mfa_enabled=user.mfa_enabled,
        )

    async def assign_role(self, public_id: str, role_code: str, ctx: AuditContext) -> AdminUserDetail:
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        role = await self.users.get_role_by_code(role_code)
        if role is None:
            raise NotFoundError("Role was not found.")

        existing = await self.users.get_user_role(user.id, role.id)
        if existing is None:
            self.users.add_user_role(UserRole(user_id=user.id, role_id=role.id, granted_at=utcnow()))
            # Privilege escalation is a named threat (spec §22.5) — role assignment is always
            # audited, not just "mutations in general", regardless of how small this diff looks.
            self.audit.record(
                ctx, action="assign_role", resource_type="user", resource_id=user.id,
                before=None, after={"role_code": role_code},
            )
            await self.session.commit()
        return await self.get_user(public_id)

    async def revoke_role(self, public_id: str, role_code: str, ctx: AuditContext) -> AdminUserDetail:
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        role = await self.users.get_role_by_code(role_code)
        if role is None:
            raise NotFoundError("Role was not found.")

        existing = await self.users.get_user_role(user.id, role.id)
        if existing is not None:
            await self.users.remove_user_role(existing)
            self.audit.record(
                ctx, action="revoke_role", resource_type="user", resource_id=user.id,
                before={"role_code": role_code}, after=None,
            )
            await self.session.commit()
        return await self.get_user(public_id)

    async def suspend(
        self, public_id: str, *, actor_public_id: str, reason: str | None, ctx: AuditContext
    ) -> AdminUserDetail:
        if public_id == actor_public_id:
            raise ConflictError("You cannot suspend your own account.")
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User was not found.")

        before_status = user.status
        user.status = "suspended"
        await self.refresh_tokens.revoke_all_for_user(user.id, reason="admin_suspend")
        self.audit.record(
            ctx, action="suspend", resource_type="user", resource_id=user.id,
            before={"status": before_status, "reason": reason}, after={"status": "suspended"},
        )
        await self.session.commit()
        return await self.get_user(public_id)

    async def reactivate(self, public_id: str, ctx: AuditContext) -> AdminUserDetail:
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User was not found.")
        before_status = user.status
        user.status = "active"
        self.audit.record(
            ctx, action="reactivate", resource_type="user", resource_id=user.id,
            before={"status": before_status}, after={"status": "active"},
        )
        await self.session.commit()
        return await self.get_user(public_id)
