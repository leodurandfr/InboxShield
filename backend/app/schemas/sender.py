import uuid
from datetime import datetime

from pydantic import BaseModel


class CategoryStatEntry(BaseModel):
    category: str
    count: int
    corrected_count: int


class SenderResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    email_address: str
    display_name: str | None
    domain: str | None
    primary_category: str | None
    total_emails: int
    last_email_at: datetime | None
    is_newsletter: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SenderDetailResponse(SenderResponse):
    category_stats: list[CategoryStatEntry] = []


class SenderBlockRequest(BaseModel):
    is_blocked: bool
