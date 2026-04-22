import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class AccountCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    imap_host: str | None = None
    imap_port: int | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    password: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    is_active: bool | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    provider: str | None
    imap_host: str
    imap_port: int
    smtp_host: str | None
    smtp_port: int | None
    username: str
    use_ssl: bool
    is_active: bool
    last_poll_at: datetime | None
    last_poll_error: str | None
    folder_mapping: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestConnectionRequest(BaseModel):
    email: EmailStr
    password: str
    imap_host: str | None = None
    imap_port: int | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    provider: str | None = None
    folders: list[str] | None = None
    suggested_mapping: dict[str, str] | None = None
    error: str | None = None
    message: str | None = None


class FolderMappingUpdate(BaseModel):
    folder_mapping: dict[str, str]


class CategoryActionsUpdate(BaseModel):
    default_category_action: dict
