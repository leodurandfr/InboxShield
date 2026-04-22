import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Rule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rules"

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'structured' or 'natural'
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    conditions: Mapped[dict | None] = mapped_column(JSONB)
    natural_text: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[list] = mapped_column(JSONB, nullable=False)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    last_matched_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))

    account: Mapped["Account | None"] = relationship(back_populates="rules")  # noqa: F821

    __table_args__ = (
        Index("idx_rules_account_active", "account_id", "is_active"),
        Index("idx_rules_priority", "priority"),
    )
