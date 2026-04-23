"""Dynamic confidence-threshold adjustment (Phase 3 — stub).

Evaluates recent correction rate and nudges settings.confidence_threshold
up or down within [0.5, 0.95]. Safe to call when there are no corrections —
it returns a no-op result.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classification import Classification, Correction
from app.models.settings import Settings

logger = logging.getLogger(__name__)

_LOWER_BOUND = 0.5
_UPPER_BOUND = 0.95
_STEP = 0.03
_HIGH_CORRECTION_RATE = 0.15  # > 15% → raise threshold
_LOW_CORRECTION_RATE = 0.05  # < 5% → lower threshold


async def evaluate_and_adjust_threshold(db: AsyncSession) -> dict:
    """Look at the last 7 days, compare corrections vs classifications, adjust."""
    since = datetime.now(UTC) - timedelta(days=7)

    total_classified = (
        await db.execute(
            select(func.count())
            .select_from(Classification)
            .where(Classification.created_at >= since)
        )
    ).scalar() or 0

    total_corrected = (
        await db.execute(
            select(func.count()).select_from(Correction).where(Correction.created_at >= since)
        )
    ).scalar() or 0

    if total_classified < 20:
        return {
            "status": "skipped",
            "reason": "not_enough_data",
            "total_classified": total_classified,
            "total_corrected": total_corrected,
        }

    rate = total_corrected / total_classified

    settings = (await db.execute(select(Settings).where(Settings.id == 1))).scalar_one_or_none()
    if settings is None:
        return {"status": "skipped", "reason": "no_settings"}

    old_threshold = settings.confidence_threshold
    new_threshold = old_threshold

    if rate > _HIGH_CORRECTION_RATE and old_threshold < _UPPER_BOUND:
        new_threshold = min(_UPPER_BOUND, round(old_threshold + _STEP, 2))
    elif rate < _LOW_CORRECTION_RATE and old_threshold > _LOWER_BOUND:
        new_threshold = max(_LOWER_BOUND, round(old_threshold - _STEP, 2))

    changed = new_threshold != old_threshold
    if changed:
        settings.confidence_threshold = new_threshold

    return {
        "status": "adjusted" if changed else "unchanged",
        "old_threshold": old_threshold,
        "new_threshold": new_threshold,
        "correction_rate": round(rate, 3),
        "total_classified": total_classified,
        "total_corrected": total_corrected,
    }
