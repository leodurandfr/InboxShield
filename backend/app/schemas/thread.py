import uuid
from datetime import datetime

from pydantic import BaseModel


class ThreadResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    subject_normalized: str | None
    participants: list | None
    email_count: int
    last_email_at: datetime | None
    awaiting_reply: bool
    awaiting_response: bool
    reply_needed_since: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThreadStatsResponse(BaseModel):
    total: int
    awaiting_reply: int
    awaiting_response: int
    oldest_awaiting: datetime | None
