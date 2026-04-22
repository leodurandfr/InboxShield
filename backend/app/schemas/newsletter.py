import uuid
from datetime import datetime

from pydantic import BaseModel


class NewsletterResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str | None
    sender_address: str
    unsubscribe_link: str | None
    unsubscribe_mailto: str | None
    unsubscribe_method: str | None
    subscription_status: str
    total_received: int
    total_read: int
    frequency_days: float | None
    last_received_at: datetime | None
    unsubscribed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NewsletterStatsResponse(BaseModel):
    total: int
    subscribed: int
    unsubscribed: int
    read_rate: float
    never_read: int


class UnsubscribeRequest(BaseModel):
    newsletter_ids: list[uuid.UUID]


class UnsubscribeResult(BaseModel):
    newsletter_id: uuid.UUID
    status: str
    message: str | None = None


class UnsubscribeResponse(BaseModel):
    success: int
    failed: int
    results: list[UnsubscribeResult]
