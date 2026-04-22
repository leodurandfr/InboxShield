from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    period: str
    emails_received: int
    emails_today: int
    review_pending: int
    phishing_blocked: int
    spam_filtered: int
    auto_classification_rate: float
    newsletters_tracked: int


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    percentage: float


class CategoriesResponse(BaseModel):
    period: str
    total: int
    categories: list[CategoryBreakdown]


class DailyVolume(BaseModel):
    date: str
    total: int
    by_category: dict[str, int]


class VolumeResponse(BaseModel):
    period: str
    days: list[DailyVolume]


class TopSender(BaseModel):
    email_address: str
    display_name: str | None
    total_emails: int
    primary_category: str | None
    last_email_at: str | None


class TopSendersResponse(BaseModel):
    limit: int
    senders: list[TopSender]


class ConfusionEntry(BaseModel):
    original: str
    corrected: str
    count: int


class ConfusionMatrixResponse(BaseModel):
    period: str
    total_corrections: int
    entries: list[ConfusionEntry]


class PerformanceMetrics(BaseModel):
    period: str
    avg_processing_time_ms: float
    review_rate: float
    classified_by_method: dict[str, int]
    total_tokens_used: int


class HourlyHeatmapEntry(BaseModel):
    day_of_week: int  # 0 = Monday … 6 = Sunday
    hour: int  # 0-23
    count: int


class HourlyHeatmapResponse(BaseModel):
    period: str
    entries: list[HourlyHeatmapEntry]
