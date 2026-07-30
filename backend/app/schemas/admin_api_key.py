import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1)
    ip_allowlist: list[str] | None = None
    expires_at: datetime.datetime | None = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    ip_allowlist: list[str] | None
    expires_at: datetime.datetime | None
    last_used_at: datetime.datetime | None
    revoked_at: datetime.datetime | None
    created_at: datetime.datetime


class ApiKeyCreatedOut(ApiKeyOut):
    """Returned only once, from the create endpoint — the raw key is never retrievable again."""

    raw_key: str
