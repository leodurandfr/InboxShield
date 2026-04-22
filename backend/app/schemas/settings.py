from datetime import date

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_temperature: float
    polling_interval_minutes: int
    confidence_threshold: float
    auto_mode: bool
    max_few_shot_examples: int
    body_excerpt_length: int
    retention_days: int
    email_retention_days: int
    phishing_auto_quarantine: bool
    initial_fetch_since: date | None
    has_api_key: bool  # True if LLM API key is configured
    has_app_password: bool  # True if app_password is set, never expose the value

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None  # Plain text, will be encrypted before storage
    llm_temperature: float | None = None
    polling_interval_minutes: int | None = None
    confidence_threshold: float | None = None
    auto_mode: bool | None = None
    max_few_shot_examples: int | None = None
    body_excerpt_length: int | None = None
    retention_days: int | None = None
    email_retention_days: int | None = None
    phishing_auto_quarantine: bool | None = None
    initial_fetch_since: date | None = None
    app_password: str | None = None  # Plain text, will be hashed before storage


class LLMModelInfo(BaseModel):
    name: str
    size: str | None = None
    modified_at: str | None = None


class LLMModelsResponse(BaseModel):
    provider: str
    models: list[LLMModelInfo]


class LLMTestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    latency_ms: int | None = None
    error: str | None = None
