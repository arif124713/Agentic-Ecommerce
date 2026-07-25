import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import (
    EmailVerificationToken,
    LoginAttempt,
    PasswordResetToken,
    RefreshToken,
    Role,
    User,
    UserRole,
)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_public_id(self, public_id: str) -> User | None:
        stmt = select(User).where(User.public_id == public_id, User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_roles_and_permissions(self, user_id: int) -> tuple[list[str], list[str]]:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .options(selectinload(Role.permissions))
        )
        roles = list((await self.session.execute(stmt)).scalars().all())
        role_codes = [r.code for r in roles]
        permission_codes = sorted({p.code for r in roles for p in r.permissions})
        return role_codes, permission_codes

    def add(self, user: User) -> None:
        self.session.add(user)

    async def assign_role(self, *, user_id: int, role_code: str) -> None:
        role_id = (await self.session.execute(select(Role.id).where(Role.code == role_code))).scalar_one()
        self.session.add(
            UserRole(user_id=user_id, role_id=role_id, granted_at=datetime.datetime.now(datetime.UTC))
        )


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, token: RefreshToken) -> None:
        self.session.add(token)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_public_id_for_user(self, public_id: str, user_id: int) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.public_id == public_id, RefreshToken.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active_for_user(self, user_id: int) -> list[RefreshToken]:
        now = datetime.datetime.now(datetime.UTC)
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def revoke(self, token: RefreshToken, *, reason: str) -> None:
        token.revoked_at = datetime.datetime.now(datetime.UTC)
        token.revoked_reason = reason

    async def revoke_family(self, family_id: str, *, reason: str) -> None:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        for token in (await self.session.execute(stmt)).scalars().all():
            token.revoked_at = now
            token.revoked_reason = reason

    async def revoke_all_for_user(self, user_id: int, *, reason: str) -> None:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        for token in (await self.session.execute(stmt)).scalars().all():
            token.revoked_at = now
            token.revoked_reason = reason


class OneTimeTokenRepository:
    """Shared create/consume logic for email-verification and password-reset tokens —
    identical shape, different table, so one generic repository instantiated per model
    avoids duplicating the same six lines twice (spec §8.3 both tables are `token_hash`,
    `expires_at`, `used_at`)."""

    def __init__(self, session: AsyncSession, model: type[EmailVerificationToken] | type[PasswordResetToken]):
        self.session = session
        self.model = model

    def create(self, *, user_id: int, token_hash: str, ttl_seconds: int):
        now = datetime.datetime.now(datetime.UTC)
        record = self.model(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=now + datetime.timedelta(seconds=ttl_seconds),
            created_at=now,
        )
        self.session.add(record)
        return record

    async def get_valid(self, token_hash: str):
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(self.model).where(
            self.model.token_hash == token_hash,
            self.model.used_at.is_(None),
            self.model.expires_at > now,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def invalidate_all_for_user(self, user_id: int) -> None:
        stmt = delete(self.model).where(self.model.user_id == user_id, self.model.used_at.is_(None))
        await self.session.execute(stmt)


class LoginAttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def record(self, *, email_hash: str, ip: str | None, success: bool, reason: str | None) -> None:
        self.session.add(
            LoginAttempt(
                email_hash=email_hash,
                ip=ip,
                success=success,
                reason=reason,
                created_at=datetime.datetime.now(datetime.UTC),
            )
        )

    async def count_recent_failures(self, *, email_hash: str, ip: str | None, since: datetime.datetime) -> int:
        stmt = select(func.count()).where(
            LoginAttempt.email_hash == email_hash,
            LoginAttempt.ip == ip,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
        return (await self.session.execute(stmt)).scalar_one()
