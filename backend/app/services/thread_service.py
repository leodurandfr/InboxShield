"""Email threading — stub for Phase 1.

Reply tracking logic (Phase 3) will build on these primitives. For now we
resolve a thread by Message-ID / In-Reply-To / References and fall back
to a new thread per email so the scheduler's import graph is valid.
"""

import logging
import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import Email, EmailThread

logger = logging.getLogger(__name__)

_SUBJECT_PREFIX_RE = re.compile(r"^\s*(re|fwd?|tr)\s*:\s*", re.IGNORECASE)


def normalize_subject(subject: str | None) -> str:
    if not subject:
        return ""
    current = subject.strip()
    # Strip Re:/Fwd: prefixes iteratively (max 5 iterations)
    for _ in range(5):
        new = _SUBJECT_PREFIX_RE.sub("", current)
        if new == current:
            break
        current = new
    return current.strip()


async def resolve_or_create_thread(
    db: AsyncSession,
    account_id: uuid.UUID,
    message_id: str | None,
    in_reply_to: str | None,
    references: str | None,
    subject: str | None,
    from_address: str | None,
    to_addresses: list | None,
    email_date: datetime | None,
) -> uuid.UUID | None:
    """Find an existing thread for this email, or create a new one.

    Steps:
    1. In-Reply-To match on existing email.message_id → reuse its thread
    2. References match on any existing email.message_id → reuse its thread
    3. Normalized subject + same account match → reuse
    4. Otherwise create a new thread.
    """
    parent_email: Email | None = None

    if in_reply_to:
        result = await db.execute(
            select(Email)
            .where(Email.account_id == account_id, Email.message_id == in_reply_to)
            .limit(1)
        )
        parent_email = result.scalar_one_or_none()

    if parent_email is None and references:
        for ref in reversed(references.split()):
            result = await db.execute(
                select(Email)
                .where(Email.account_id == account_id, Email.message_id == ref)
                .limit(1)
            )
            parent_email = result.scalar_one_or_none()
            if parent_email is not None:
                break

    if parent_email is not None and parent_email.thread_id:
        return parent_email.thread_id

    normalized = normalize_subject(subject)
    if normalized:
        result = await db.execute(
            select(EmailThread)
            .where(
                EmailThread.account_id == account_id,
                EmailThread.subject_normalized == normalized,
            )
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing.id

    # Build participants list
    participants: list[str] = []
    if from_address:
        participants.append(from_address)
    if to_addresses:
        participants.extend(a for a in to_addresses if isinstance(a, str))

    thread = EmailThread(
        account_id=account_id,
        subject_normalized=normalized or None,
        participants=participants or None,
        email_count=1,
        last_email_at=email_date,
    )
    db.add(thread)
    await db.flush()
    return thread.id


async def update_thread_reply_status(
    db: AsyncSession,
    thread_id: uuid.UUID,
    from_address: str | None,
    to_addresses: list | None,
    user_email: str | None,
    email_date: datetime | None,
) -> None:
    """Stub — Phase 3 will compute awaiting_reply / awaiting_response here."""
    result = await db.execute(select(EmailThread).where(EmailThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if thread is None:
        return
    if email_date and (thread.last_email_at is None or email_date > thread.last_email_at):
        thread.last_email_at = email_date
    thread.email_count = (thread.email_count or 0) + 1
