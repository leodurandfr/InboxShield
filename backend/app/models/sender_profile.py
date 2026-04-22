import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class SenderProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sender_profiles"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255))
    primary_category: Mapped[str | None] = mapped_column(String(50))
    total_emails: Mapped[int] = mapped_column(Integer, default=0)
    last_email_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_newsletter: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    category_stats: Mapped[list["SenderCategoryStats"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    newsletter: Mapped["Newsletter | None"] = relationship(  # noqa: F821
        back_populates="sender_profile", uselist=False
    )

    __table_args__ = (
        Index(
            "idx_sender_profiles_address",
            "account_id",
            "email_address",
            unique=True,
        ),
        Index("idx_sender_profiles_domain", "domain"),
        Index(
            "idx_sender_profiles_blocked",
            "is_blocked",
            postgresql_where="is_blocked = TRUE",
        ),
    )


class SenderCategoryStats(Base, UUIDMixin):
    __tablename__ = "sender_category_stats"

    sender_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sender_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)
    corrected_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["SenderProfile"] = relationship(back_populates="category_stats")

    __table_args__ = (
        Index(
            "idx_sender_cat_stats_profile_cat",
            "sender_profile_id",
            "category",
            unique=True,
        ),
    )
