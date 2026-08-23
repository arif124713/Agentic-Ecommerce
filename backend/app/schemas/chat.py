import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreateIn(BaseModel):
    agent: str = Field(pattern="^(stylist|support|insights)$")


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(validation_alias="public_id")
    agent: str
    expires_at: datetime.datetime


class ChatMessageIn(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    stream: bool = True


class ToolTraceOut(BaseModel):
    server: str
    tool: str
    ms: int
    ok: bool
    error: str | None = None
    returned: int | None = None


class ChatResponseOut(BaseModel):
    message_id: str
    session_id: str
    agent: str
    role: str = "assistant"
    content: str
    blocks: list[dict] = Field(default_factory=list)
    tool_trace: list[ToolTraceOut] = Field(default_factory=list)
    relaxation_applied: list[str] = Field(default_factory=list)
    created_at: datetime.datetime
