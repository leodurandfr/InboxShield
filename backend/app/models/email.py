import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EmailThread(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_threads"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    subject_normalized: Mapped[str | None] = mapped_column(String(512))
    participants: Mapped[list | None] = mapped_column(JSONB)
    email_count: Mapped[int] = mapped_column(Integer, default=1)
    last_email_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    awaiting_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    awaiting_response: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_needed_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    emails: Mapped[list["Email"]] = relationship(back_populates="thread")

    __table_args__ = (
        Index("idx_threads_account_id", "account_id"),
        Index(
            "idx_threads_awaiting",
            "awaiting_reply",
            "awaiting_response",
            postgresql_where=(
                "awaiting_reply = TRUE OR awaiting_response = TRUE"
            ),
        ),
    )


class Email(Base, UUIDMixin):
    __tablename__ = "emails"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id", ondelete="SET NULL")
    )
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(512))
    in_reply_to: Mapped[str | None] = mapped_column(String(512))
    references: Mapped[str | None] = mapped_column(Text)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255))
    reply_to: Mapped[str | None] = mapped_column(String(255))
    to_addresses: Mapped[list | None] = mapped_column(JSONB)
    cc_addresses: Mapped[list | None] = mapped_column(JSONB)
    subject: Mapped[str | None] = mapped_column(Text)
    body_excerpt: Mapped[str | None] = mapped_column(Text)
    body_html_excerpt: Mapped[str | None] = mapped_column(Text)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    attachment_names: Mapped[list | None] = mapped_column(JSONB)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    folder: Mapped[str | None] = mapped_column(String(255))
    original_folder: Mapped[str | None] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="emails")  # noqa: F821
    thread: Mapped["EmailThread | None"] = relationship(back_populates="emails")
    classification: Mapped["Classification | None"] = relationship(  # noqa: F821
        back_populates="email", uselist=False, cascade="all, delete-orphan"
    )
    actions: Mapped[list["Action"]] = relationship(back_populates="email", cascade="all, delete-orphan")  # noqa: F821
    urls: Mapped[list["EmailUrl"]] = relationship(back_populates="email", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_emails_account_uid", "account_id", "uid", unique=True),
        Index("idx_emails_from_address", "from_address"),
        Index("idx_emails_date", "date"),
        Index("idx_emails_folder", "folder"),
        Index("idx_emails_account_date", "account_id", "date"),
        Index("idx_emails_processing_status", "processing_status"),
        Index("idx_emails_thread_id", "thread_id"),
        Index("idx_emails_message_id", "message_id"),
        Index(
            "idx_emails_not_archived",
            "is_archived",
            postgresql_where="is_archived = FALSE",
        ),
    )


class EmailUrl(Base, UUIDMixin):
    __tablename__ = "email_urls"

    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    display_text: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(255))
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    suspicion_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    email: Mapped["Email"] = relationship(back_populates="urls")

    __table_args__ = (
        Index("idx_email_urls_email_id", "email_id"),
        Index(
            "idx_email_urls_suspicious",
            "is_suspicious",
            postgresql_where="is_suspicious = TRUE",
        ),
    )
