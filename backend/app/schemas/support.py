import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreateIn(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


class TicketMessageIn(BaseModel):
    body: str = Field(min_length=1)


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_type: str
    body: str
    created_at: datetime.datetime


class TicketOut(BaseModel):
    """Customer-facing view — addressed by `public_id`, never the internal `id` (spec §8.1)."""

    model_config = ConfigDict(from_attributes=True)

    public_id: str
    subject: str
    status: str
    priority: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    messages: list[TicketMessageOut]


class TicketListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    subject: str
    status: str
    priority: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
