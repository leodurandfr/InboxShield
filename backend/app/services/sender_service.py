"""Sender profile management: create, update stats, direct classification."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sender_profile import SenderCategoryStats, SenderProfile

logger = logging.getLogger(__name__)


async def get_or_create_sender_profile(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_address: str,
    display_name: str | None = None,
) -> SenderProfile:
    """Get existing sender profile or create a new one."""
    stmt = select(SenderProfile).where(
        SenderProfile.account_id == account_id,
        SenderProfile.email_address == email_address,
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None:
        domain = email_address.rsplit("@", 1)[-1].lower() if "@" in email_address else None
        profile = SenderProfile(
            account_id=account_id,
            email_address=email_address,
            display_name=display_name,
            domain=domain,
            total_emails=0,
        )
        db.add(profile)
        await db.flush()

    # Update display name if provided and different
    if display_name and display_name != profile.display_name:
        profile.display_name = display_name

    return profile


async def update_sender_stats(
    db: AsyncSession,
    profile: SenderProfile,
    category: str,
    is_correction: bool = False,
) -> None:
    """Update sender category stats after a classification or correction."""
    # Get or create category stats
    stmt = select(SenderCategoryStats).where(
        SenderCategoryStats.sender_profile_id == profile.id,
        SenderCategoryStats.category == category,
    )
    result = await db.execute(stmt)
    stats = result.scalar_one_or_none()

    if stats is None:
        stats = SenderCategoryStats(
            sender_profile_id=profile.id,
            category=category,
            count=0,
            corrected_count=0,
        )
        db.add(stats)

    stats.count += 1
    if is_correction:
        stats.corrected_count += 2  # Double weight for corrections
    stats.last_seen_at = datetime.now(UTC)

    # Update profile totals and primary category
    await _refresh_profile_stats(db, profile)


async def _refresh_profile_stats(db: AsyncSession, profile: SenderProfile) -> None:
    """Recalculate total_emails and primary_category from category stats."""
    stmt = select(SenderCategoryStats).where(SenderCategoryStats.sender_profile_id == profile.id)
    result = await db.execute(stmt)
    all_stats = result.scalars().all()

    if not all_stats:
        return

    total = sum(s.count for s in all_stats)
    profile.total_emails = total
    profile.last_email_at = datetime.now(UTC)

    # Find dominant category (weighted: count + corrected_count)
    dominant = max(all_stats, key=lambda s: s.count + s.corrected_count)
    profile.primary_category = dominant.category


async def try_direct_classification(
    db: AsyncSession,
    account_id: uuid.UUID,
    from_address: str,
) -> str | None:
    """Try to classify directly from sender profile (no LLM needed).

    Returns category if sender has a dominant category (count >= 5 and > 80% of total).
    Returns None if LLM classification is needed.
    """
    stmt = select(SenderProfile).where(
        SenderProfile.account_id == account_id,
        SenderProfile.email_address == from_address,
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None:
        return None

    # Load category stats
    stats_stmt = select(SenderCategoryStats).where(
        SenderCategoryStats.sender_profile_id == profile.id
    )
    stats_result = await db.execute(stats_stmt)
    all_stats = stats_result.scalars().all()

    if not all_stats:
        return None

    total = sum(s.count + s.corrected_count for s in all_stats)
    if total < 5:
        return None

    # Find dominant category
    dominant = max(all_stats, key=lambda s: s.count + s.corrected_count)
    dominant_weight = dominant.count + dominant.corrected_count
    ratio = dominant_weight / total

    if ratio > 0.8:
        logger.debug(
            "Direct classification for %s: %s (%.0f%%, n=%d)",
            from_address,
            dominant.category,
            ratio * 100,
            total,
        )
        return dominant.category

    # Multiple significant categories — need LLM for context
    return None


async def is_sender_blocked(
    db: AsyncSession,
    account_id: uuid.UUID,
    from_address: str,
) -> bool:
    """Check if a sender is blocked."""
    stmt = select(SenderProfile.is_blocked).where(
        SenderProfile.account_id == account_id,
        SenderProfile.email_address == from_address,
    )
    result = await db.execute(stmt)
    is_blocked = result.scalar_one_or_none()
    return bool(is_blocked)


async def block_sender(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_address: str,
) -> SenderProfile:
    """Block a sender."""
    profile = await get_or_create_sender_profile(db, account_id, email_address)
    profile.is_blocked = True
    return profile


async def unblock_sender(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_address: str,
) -> SenderProfile | None:
    """Unblock a sender."""
    stmt = select(SenderProfile).where(
        SenderProfile.account_id == account_id,
        SenderProfile.email_address == email_address,
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile:
        profile.is_blocked = False
    return profile
