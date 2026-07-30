import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_role: str | None
    action: str
    resource_type: str
    resource_id: str
    before_json: dict | None
    after_json: dict | None
    ip: str | None
    request_id: str | None
    created_at: datetime.datetime
