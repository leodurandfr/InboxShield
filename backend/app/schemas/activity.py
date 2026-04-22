import uuid
from datetime import datetime

from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    email_id: uuid.UUID | None
    event_type: str
    severity: str
    title: str
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
