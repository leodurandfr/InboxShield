import uuid

from pydantic import BaseModel


class ReviewApproveRequest(BaseModel):
    """Optional body — an empty POST is accepted too."""


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
