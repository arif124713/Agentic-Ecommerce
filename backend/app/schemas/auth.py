import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    marketing_opt_in: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class EmailVerifyIn(BaseModel):
    token: str


class EmailResendIn(BaseModel):
    email: EmailStr


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    first_name: str
    last_name: str | None
    email: str
    email_verified_at: datetime.datetime | None
    mfa_enabled: bool
    roles: list[str]
    permissions: list[str]


class SessionOut(BaseModel):
    id: str
    device_label: str | None
    ip: str | None
    is_current: bool
    created_at: datetime.datetime
    last_used_at: datetime.datetime | None
