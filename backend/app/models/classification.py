import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

# Valid categories
CATEGORIES = [
    "important",
    "work",
    "personal",
    "newsletter",
    "promotion",
    "notification",
    "spam",
    "phishing",
    "transactional",
]


class Classification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "classifications"

    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    is_spam: Mapped[bool] = mapped_column(default=False)
    is_phishing: Mapped[bool] = mapped_column(default=False)
    phishing_reasons: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    classified_by: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="SET NULL")
    )
    llm_provider: Mapped[str | None] = mapped_column(String(50))
    llm_model: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    email: Mapped["Email"] = relationship(back_populates="classification")  # noqa: F821
    corrections: Mapped[list["Correction"]] = relationship(
        back_populates="classification", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_classifications_category", "category"),
        Index("idx_classifications_status", "status"),
        Index(
            "idx_classifications_is_phishing",
            "is_phishing",
            postgresql_where="is_phishing = TRUE",
        ),
        Index(
            "idx_classifications_review",
            "status",
            postgresql_where="status = 'review'",
        ),
    )


class Correction(Base, UUIDMixin):
    __tablename__ = "corrections"

    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    classification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classifications.id", ondelete="CASCADE"), nullable=False
    )
    original_category: Mapped[str] = mapped_column(String(50), nullable=False)
    corrected_category: Mapped[str] = mapped_column(String(50), nullable=False)
    original_confidence: Mapped[float | None] = mapped_column(Float)
    user_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    classification: Mapped["Classification"] = relationship(back_populates="corrections")

    __table_args__ = (
        Index("idx_corrections_categories", "original_category", "corrected_category"),
        Index("idx_corrections_created_at", "created_at"),
    )
