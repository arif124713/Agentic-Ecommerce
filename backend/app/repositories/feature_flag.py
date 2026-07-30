from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flag import FeatureFlag


class FeatureFlagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[FeatureFlag]:
        stmt = select(FeatureFlag).order_by(FeatureFlag.key)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_key(self, key: str) -> FeatureFlag | None:
        return await self.session.get(FeatureFlag, key)

    def add(self, flag: FeatureFlag) -> None:
        self.session.add(flag)
