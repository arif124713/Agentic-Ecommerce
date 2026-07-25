from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import Role, User, UserRole


class AdminUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_users(self, *, q: str | None, page: int, per_page: int) -> tuple[list[User], int]:
        stmt = select(User).where(User.deleted_at.is_(None))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(User.email.ilike(like), User.first_name.ilike(like), User.last_name.ilike(like))
            )

        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.options(selectinload(User.user_roles).selectinload(UserRole.role))
            .order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def get_by_public_id(self, public_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.public_id == public_id, User.deleted_at.is_(None))
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_role_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_user_role(self, user_id: int, role_id: int) -> UserRole | None:
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_user_role(self, user_role: UserRole) -> None:
        self.session.add(user_role)

    async def remove_user_role(self, user_role: UserRole) -> None:
        await self.session.delete(user_role)
