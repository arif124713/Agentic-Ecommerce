import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import ApiKey


class ApiKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, key: ApiKey) -> None:
        self.session.add(key)

    async def list_all(self) -> list[ApiKey]:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_public_id(self, public_id: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.public_id == public_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active_candidates(self) -> list[ApiKey]:
        """Every non-revoked, non-expired key — the auth dependency has to check each one's hash
        in turn since the raw key (and therefore which row it belongs to) isn't known until a
        candidate's argon2 hash actually matches, so there's no indexed lookup to do instead."""
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(ApiKey).where(
            ApiKey.revoked_at.is_(None),
            (ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now),
        )
        return list((await self.session.execute(stmt)).scalars().all())
