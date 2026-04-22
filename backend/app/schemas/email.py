import uuid
from datetime import datetime

from pydantic import BaseModel


class ClassificationSummary(BaseModel):
    category: str
    confidence: float
    status: str
    classified_by: str

    model_config = {"from_attributes": True}


class EmailResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    from_address: str
    from_name: str | None
    subject: str | None
    date: datetime
    folder: str | None
    is_read: bool
    is_flagged: bool
    has_attachments: bool
    processing_status: str
    classification: ClassificationSummary | None = None

    model_config = {"from_attributes": True}


class EmailDetailResponse(EmailResponse):
    to_addresses: list[str] | None
    cc_addresses: list[str] | None
    body_excerpt: str | None
    attachment_names: list[str] | None
    original_folder: str | None
    size_bytes: int | None
    message_id: str | None
    thread_id: uuid.UUID | None
    created_at: datetime


class EmailMoveRequest(BaseModel):
    folder: str


class EmailFlagRequest(BaseModel):
    flag: str  # read, unread, important


class BulkActionRequest(BaseModel):
    email_ids: list[uuid.UUID]
    action: dict  # {"type": "move", "folder": "..."} or {"type": "flag", "value": "read"}


class BulkActionResult(BaseModel):
    email_id: uuid.UUID
    status: str


class BulkActionResponse(BaseModel):
    success: int
    failed: int
    results: list[BulkActionResult]
