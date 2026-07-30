from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagWriteIn(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
    enabled: bool = False
    rollout_percent: int = Field(default=0, ge=0, le=100)
    targeting: dict | None = None
    description: str | None = None


class FeatureFlagUpdateIn(BaseModel):
    enabled: bool = False
    rollout_percent: int = Field(default=0, ge=0, le=100)
    targeting: dict | None = None
    description: str | None = None


class FeatureFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    enabled: bool
    rollout_percent: int
    targeting: dict | None
    description: str | None
    updated_by: int | None
