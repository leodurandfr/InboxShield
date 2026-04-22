import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Account(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(50))
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer, default=587)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poll_error: Mapped[str | None] = mapped_column(Text)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0)
    folder_mapping: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    settings: Mapped["AccountSettings | None"] = relationship(
        back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    emails: Mapped[list["Email"]] = relationship(  # noqa: F821
        back_populates="account", cascade="all, delete-orphan"
    )
    rules: Mapped[list["Rule"]] = relationship(  # noqa: F821
        back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_accounts_email", "email"),
        Index("idx_accounts_is_active", "is_active"),
    )


class AccountSettings(Base, UUIDMixin):
    __tablename__ = "account_settings"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    default_category_action: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    account: Mapped["Account"] = relationship(back_populates="settings")
