from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditContext
from app.core.errors import ConflictError, NotFoundError
from app.models.feature_flag import FeatureFlag
from app.repositories.audit import AuditLogRepository
from app.repositories.feature_flag import FeatureFlagRepository
from app.schemas.admin_feature_flag import FeatureFlagOut, FeatureFlagUpdateIn, FeatureFlagWriteIn


class AdminFeatureFlagService:
    """spec §28: boolean + rollout_percent + targeting, editable by Super Admins only
    (system:feature_flag:write — the single strictest permission in the matrix, granted to no
    role but super_admin). No Redis 30s cache here (documented gap, same shape as every other
    Redis-dependent feature in this project) — every read is a fresh query."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.flags = FeatureFlagRepository(session)
        self.audit = AuditLogRepository(session)

    async def list_flags(self) -> list[FeatureFlagOut]:
        return [FeatureFlagOut.model_validate(f) for f in await self.flags.list_all()]

    async def get_flag(self, key: str) -> FeatureFlagOut:
        flag = await self.flags.get_by_key(key)
        if flag is None:
            raise NotFoundError("Feature flag was not found.")
        return FeatureFlagOut.model_validate(flag)

    async def create_flag(self, payload: FeatureFlagWriteIn, ctx: AuditContext) -> FeatureFlagOut:
        if await self.flags.get_by_key(payload.key) is not None:
            raise ConflictError(f"A feature flag with key '{payload.key}' already exists.")
        flag = FeatureFlag(**payload.model_dump(), updated_by=ctx.actor_user_id)
        self.flags.add(flag)
        self.audit.record(
            ctx, action="create", resource_type="feature_flag", resource_id=flag.key,
            before=None, after=self._snapshot(flag),
        )
        await self.session.commit()
        return FeatureFlagOut.model_validate(flag)

    async def update_flag(self, key: str, payload: FeatureFlagUpdateIn, ctx: AuditContext) -> FeatureFlagOut:
        flag = await self.flags.get_by_key(key)
        if flag is None:
            raise NotFoundError("Feature flag was not found.")
        before = self._snapshot(flag)
        for field, value in payload.model_dump().items():
            setattr(flag, field, value)
        flag.updated_by = ctx.actor_user_id
        self.audit.record(
            ctx, action="update", resource_type="feature_flag", resource_id=key,
            before=before, after=self._snapshot(flag),
        )
        await self.session.commit()
        return FeatureFlagOut.model_validate(flag)

    @staticmethod
    def _snapshot(flag: FeatureFlag) -> dict:
        return {
            "enabled": flag.enabled,
            "rollout_percent": flag.rollout_percent,
            "targeting": flag.targeting,
        }
