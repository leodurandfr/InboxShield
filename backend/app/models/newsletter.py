import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Newsletter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "newsletters"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    sender_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sender_profiles.id", ondelete="SET NULL")
    )
    name: Mapped[str | None] = mapped_column(String(255))
    sender_address: Mapped[str] = mapped_column(String(255), nullable=False)
    unsubscribe_link: Mapped[str | None] = mapped_column(Text)
    unsubscribe_mailto: Mapped[str | None] = mapped_column(String(255))
    unsubscribe_method: Mapped[str | None] = mapped_column(String(20))
    subscription_status: Mapped[str] = mapped_column(String(20), default="subscribed")
    total_received: Mapped[int] = mapped_column(Integer, default=0)
    total_read: Mapped[int] = mapped_column(Integer, default=0)
    frequency_days: Mapped[float | None] = mapped_column(Float)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender_profile: Mapped["SenderProfile | None"] = relationship(  # noqa: F821
        back_populates="newsletter"
    )

    __table_args__ = (
        Index(
            "idx_newsletters_account_sender",
            "account_id",
            "sender_address",
            unique=True,
        ),
        Index("idx_newsletters_status", "subscription_status"),
    )
