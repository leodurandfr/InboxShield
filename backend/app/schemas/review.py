import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewApproveRequest(BaseModel):
    """Optional body — an empty POST is accepted too."""


class ReviewStatsResponse(BaseModel):
    total_pending: int
    by_category: dict[str, int]
    oldest_pending: datetime | None = None


class ReviewCorrectRequest(BaseModel):
    corrected_category: str
    user_note: str | None = None


class BulkApproveRequest(BaseModel):
    email_ids: list[uuid.UUID]


class BulkApproveResult(BaseModel):
    email_id: uuid.UUID
    status: str


class BulkApproveResponse(BaseModel):
    success: int
    failed: int
    results: list[BulkApproveResult]
