import datetime

from pydantic import BaseModel, Field

from app.schemas.support import TicketMessageOut


class AdminTicketListItemOut(BaseModel):
    public_id: str
    subject: str
    status: str
    priority: str
    contact_email: str
    assignee_name: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AdminTicketOut(BaseModel):
    public_id: str
    subject: str
    status: str
    priority: str
    contact_email: str
    assignee_user_id: int | None
    assignee_name: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    messages: list[TicketMessageOut]


class TicketStatusIn(BaseModel):
    status: str = Field(pattern="^(open|pending|resolved|closed)$")


class TicketAssignIn(BaseModel):
    assignee_user_id: int | None = None
