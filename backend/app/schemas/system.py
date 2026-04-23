from datetime import datetime

from pydantic import BaseModel


class ServiceCheck(BaseModel):
    status: str  # "ok" or "error"
    latency_ms: int | None = None
    error: str | None = None


class IMAPAccountCheck(BaseModel):
    account: str
    status: str
    last_poll: datetime | None = None
    error: str | None = None


class SchedulerInfo(BaseModel):
    running: bool
    jobs: int
    next_poll: datetime | None = None


class LoadedModel(BaseModel):
    name: str
    size_bytes: int
    size_vram_bytes: int = 0
    context_length: int
    expires_at: datetime | None = None


class OllamaManagerStatus(BaseModel):
    running: bool
    managed_by_us: bool = False
    pid: int | None = None
    binary_path: str | None = None
    install_method: str | None = None  # "homebrew" | "systemd" | "app" | "docker" | "unknown"
    service_status: str | None = None  # "running" | "stopped" | "not-installed"
    loaded_models: list[LoadedModel] = []
    installed_models: list[dict] = []
    total_disk_bytes: int = 0


class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    checks: dict  # {"database": ServiceCheck, "ollama": ServiceCheck}
    imap_accounts: list[IMAPAccountCheck]
    scheduler: SchedulerInfo
    ollama_manager: OllamaManagerStatus | None = None


class LLMStatus(BaseModel):
    configured: bool
    available: bool
    provider: str
    model: str
    error: str | None = None


class SystemStats(BaseModel):
    uptime_seconds: int
    emails_processed_today: int
    classifications_today: int
    pending_review: int
    active_accounts: int
    llm_status: LLMStatus | None = None
