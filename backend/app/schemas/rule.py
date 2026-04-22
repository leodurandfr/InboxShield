import uuid
from datetime import datetime

from pydantic import BaseModel


class RuleCreate(BaseModel):
    name: str
    type: str  # 'structured' or 'natural'
    account_id: uuid.UUID | None = None
    priority: int = 0
    category: str | None = None  # Category to assign when matched
    conditions: dict | None = None
    natural_text: str | None = None
    actions: list[dict]


class RuleUpdate(BaseModel):
    name: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    category: str | None = None
    conditions: dict | None = None
    natural_text: str | None = None
    actions: list[dict] | None = None


class RuleResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    name: str
    type: str
    priority: int
    is_active: bool
    category: str | None
    conditions: dict | None
    natural_text: str | None
    actions: list[dict]
    match_count: int
    last_matched_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleTestRequest(BaseModel):
    email_id: uuid.UUID


class RuleTestResponse(BaseModel):
    matches: bool
    matched_conditions: list[str] | None = None
    actions_preview: list[dict] | None = None


class RuleReorderRequest(BaseModel):
    rule_ids: list[uuid.UUID]  # Ordered list of rule IDs (first = highest priority)
