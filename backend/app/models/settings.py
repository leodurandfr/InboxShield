from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    llm_provider: Mapped[str] = mapped_column(String(50), default="ollama")
    llm_model: Mapped[str] = mapped_column(String(100), default="qwen2.5:7b")
    llm_base_url: Mapped[str | None] = mapped_column(String(255))
    llm_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    llm_temperature: Mapped[float] = mapped_column(Float, default=0.1)
    polling_interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    auto_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    max_few_shot_examples: Mapped[int] = mapped_column(Integer, default=10)
    body_excerpt_length: Mapped[int] = mapped_column(Integer, default=2000)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    email_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    phishing_auto_quarantine: Mapped[bool] = mapped_column(Boolean, default=True)
    initial_fetch_since: Mapped[date | None] = mapped_column(Date)
    app_password: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
