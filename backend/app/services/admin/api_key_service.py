import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core import api_keys
from app.core.audit import AuditContext
from app.core.errors import NotFoundError, ValidationAppError
from app.models.auth import ApiKey, Permission
from app.repositories.api_key import ApiKeyRepository
from app.repositories.audit import AuditLogRepository
from app.schemas.admin_api_key import ApiKeyCreateIn, ApiKeyCreatedOut, ApiKeyOut


class AdminApiKeyService:
    """spec §11.5: admin API keys are machine credentials scoped to a permission subset, never
    including iam:*/system:* (those stay human-only), displayed once at creation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.keys = ApiKeyRepository(session)
        self.audit = AuditLogRepository(session)

    async def _validate_scopes(self, scopes: list[str]) -> None:
        restricted = api_keys.restricted_scopes(scopes)
        if restricted:
            raise ValidationAppError(
                "API keys can't be granted iam:* or system:* permissions.",
                details=[{"field": "scopes", "issue": f"'{s}' is not allowed on an API key."} for s in restricted],
            )
        known = set(
            (await self.session.execute(select(Permission.code).where(Permission.code.in_(scopes)))).scalars().all()
        )
        unknown = [s for s in scopes if s not in known]
        if unknown:
            raise ValidationAppError(
                "One or more scopes are not recognised permission codes.",
                details=[{"field": "scopes", "issue": f"'{s}' is not a known permission."} for s in unknown],
            )

    async def list_keys(self) -> list[ApiKeyOut]:
        return [ApiKeyOut.model_validate(k) for k in await self.keys.list_all()]

    async def create_key(self, payload: ApiKeyCreateIn, ctx: AuditContext) -> ApiKeyCreatedOut:
        await self._validate_scopes(payload.scopes)

        raw_key, prefix = api_keys.generate_key()
        key = ApiKey(
            public_id=str(ULID()),
            name=payload.name,
            key_hash=api_keys.hash_key(raw_key),
            key_prefix=prefix,
            scopes=payload.scopes,
            ip_allowlist=payload.ip_allowlist,
            created_by_user_id=ctx.actor_user_id,
            expires_at=payload.expires_at,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self.keys.add(key)
        await self.session.flush()
        self.audit.record(
            ctx,
            action="create",
            resource_type="api_key",
            resource_id=key.public_id,
            before=None,
            after={"name": key.name, "scopes": key.scopes, "key_prefix": key.key_prefix},
        )
        await self.session.commit()
        return ApiKeyCreatedOut(
            **ApiKeyOut.model_validate(key).model_dump(),
            raw_key=raw_key,
        )

    async def revoke_key(self, public_id: str, ctx: AuditContext) -> None:
        key = await self.keys.get_by_public_id(public_id)
        if key is None:
            raise NotFoundError("API key was not found.")
        if key.revoked_at is not None:
            return
        key.revoked_at = datetime.datetime.now(datetime.UTC)
        self.audit.record(
            ctx, action="revoke", resource_type="api_key", resource_id=public_id, before=None, after=None
        )
        await self.session.commit()
