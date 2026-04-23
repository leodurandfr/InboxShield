"""Email threading + reply tracking.

Resolves threads from Message-ID / In-Reply-To / References / normalized
subject, and maintains `awaiting_reply` / `awaiting_response` flags so the
Threads UI can surface conversations that need attention.
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
    """Recompute awaiting_reply / awaiting_response flags after a new email.

    Semantics (see docs/03g-REPLY-TRACKING.md):
    - email from user → user has replied, now awaits someone else's response
    - email to user  → someone wrote, user still owes a reply
    Both flags are mutually exclusive. Non-directional emails (user neither
    sender nor recipient) just bump email_count + last_email_at.
    """
    result = await db.execute(select(EmailThread).where(EmailThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if thread is None:
        return

    # Bump counters regardless of direction
    if email_date and (thread.last_email_at is None or email_date > thread.last_email_at):
        thread.last_email_at = email_date
    thread.email_count = (thread.email_count or 0) + 1

    # Update participants list
    participants = list(thread.participants or [])
    for addr in _collect_addresses(from_address, to_addresses):
        if addr and addr not in participants:
            participants.append(addr)
    thread.participants = participants or None

    if not user_email:
        return

    user_lc = user_email.lower()
    from_lc = (from_address or "").lower()
    to_list_lc = {
        addr.lower()
        for addr in (to_addresses or [])
        if isinstance(addr, str)
    }

    is_from_user = from_lc == user_lc
    is_to_user = user_lc in to_list_lc

    if is_from_user:
        thread.awaiting_reply = False
        thread.awaiting_response = True
        thread.reply_needed_since = email_date
    elif is_to_user:
        thread.awaiting_response = False
        thread.awaiting_reply = True
        thread.reply_needed_since = email_date


def _collect_addresses(
    from_address: str | None,
    to_addresses: list | None,
) -> list[str]:
    collected: list[str] = []
    if from_address:
        collected.append(from_address)
    if to_addresses:
        collected.extend(a for a in to_addresses if isinstance(a, str))
    return collected


async def resolve_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
) -> EmailThread | None:
    """Mark a thread as resolved (used by Threads UI actions)."""
    thread = (
        await db.execute(select(EmailThread).where(EmailThread.id == thread_id))
    ).scalar_one_or_none()
    if thread is None:
        return None
    thread.awaiting_reply = False
    thread.awaiting_response = False
    thread.reply_needed_since = None
    return thread


async def ignore_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
) -> EmailThread | None:
    """Same effect as resolve, loggable separately at the caller level."""
    return await resolve_thread(db, thread_id)
