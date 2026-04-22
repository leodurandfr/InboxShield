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


class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    checks: dict  # {"database": ServiceCheck, "ollama": ServiceCheck}
    imap_accounts: list[IMAPAccountCheck]
    scheduler: SchedulerInfo


class SystemStats(BaseModel):
    uptime_seconds: int
    emails_processed_today: int
    classifications_today: int
    pending_review: int
    active_accounts: int
