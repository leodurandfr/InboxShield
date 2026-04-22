"""Newsletter detection, stats, and unsubscribe — Phase 2 stub."""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.newsletter import Newsletter

logger = logging.getLogger(__name__)


async def compute_newsletter_stats(
    db: AsyncSession,
    account_id: uuid.UUID | None = None,
) -> dict:
    """Aggregate totals for the /newsletters/stats endpoint."""
    base = select(Newsletter)
    if account_id:
        base = base.where(Newsletter.account_id == account_id)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0

    subscribed = (
        await db.execute(
            select(func.count())
            .select_from(base.where(Newsletter.subscription_status == "subscribed").subquery())
        )
    ).scalar() or 0

    unsubscribed = (
        await db.execute(
            select(func.count())
            .select_from(base.where(Newsletter.subscription_status == "unsubscribed").subquery())
        )
    ).scalar() or 0

    received_sum = (
        await db.execute(select(func.coalesce(func.sum(Newsletter.total_received), 0)))
    ).scalar() or 0
    read_sum = (
        await db.execute(select(func.coalesce(func.sum(Newsletter.total_read), 0)))
    ).scalar() or 0
    read_rate = (read_sum / received_sum) if received_sum else 0.0

    never_read = (
        await db.execute(
            select(func.count())
            .select_from(base.where(Newsletter.total_read == 0).subquery())
        )
    ).scalar() or 0

    return {
        "total": total,
        "subscribed": subscribed,
        "unsubscribed": unsubscribed,
        "read_rate": round(read_rate, 3),
        "never_read": never_read,
    }


async def unsubscribe_newsletter(
    db: AsyncSession,
    newsletter: Newsletter,
) -> dict:
    """Stub — real HTTP/mailto unsubscribe logic ships in Phase 2."""
    logger.info("Unsubscribe stub called for %s", newsletter.sender_address)
    return {
        "status": "failed",
        "message": "Désinscription non encore implémentée",
    }
