import datetime

from pydantic import BaseModel, Field


class AdminUserListItem(BaseModel):
    public_id: str
    first_name: str
    last_name: str | None
    email: str
    status: str
    roles: list[str]
    created_at: datetime.datetime


class AdminUserDetail(AdminUserListItem):
    email_verified_at: datetime.datetime | None
    last_login_at: datetime.datetime | None
    mfa_enabled: bool


class AssignRoleIn(BaseModel):
    role_code: str = Field(min_length=1, max_length=40)


class SuspendUserIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
