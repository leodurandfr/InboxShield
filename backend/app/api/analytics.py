"""API routes for analytics and statistics."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.classification import Classification
from app.models.email import Email
from app.models.newsletter import Newsletter
from app.models.sender_profile import SenderProfile
from app.schemas.analytics import (
    AnalyticsOverview,
    CategoriesResponse,
    CategoryBreakdown,
    DailyVolume,
    TopSender,
    TopSendersResponse,
    VolumeResponse,
)

router = APIRouter()


def _period_start(period: str) -> datetime:
    """Get the start datetime for a period string."""
    now = datetime.now(UTC)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    if period == "90d":
        return now - timedelta(days=90)
    return now - timedelta(days=30)  # default


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    account_id: uuid.UUID | None = None,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level analytics overview."""
    since = _period_start(period)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    base = select(Email)
    if account_id:
        base = base.where(Email.account_id == account_id)

    # Total emails in period
    total_q = select(func.count()).select_from(base.where(Email.date >= since).subquery())
    emails_received = (await db.execute(total_q)).scalar() or 0

    # Emails today
    today_q = select(func.count()).select_from(base.where(Email.date >= today_start).subquery())
    emails_today = (await db.execute(today_q)).scalar() or 0

    # Review pending
    review_q = select(func.count()).select_from(
        base.where(Email.processing_status == "pending_review").subquery()
    )
    review_pending = (await db.execute(review_q)).scalar() or 0

    # Phishing blocked (in period)
    phishing_base = (
        select(Email)
        .join(Classification, Classification.email_id == Email.id)
        .where(Classification.is_phishing == True, Email.date >= since)  # noqa: E712
    )
    if account_id:
        phishing_base = phishing_base.where(Email.account_id == account_id)
    phishing_q = select(func.count()).select_from(phishing_base.subquery())
    phishing_blocked = (await db.execute(phishing_q)).scalar() or 0

    # Spam filtered
    spam_base = (
        select(Email)
        .join(Classification, Classification.email_id == Email.id)
        .where(Classification.category == "spam", Email.date >= since)
    )
    if account_id:
        spam_base = spam_base.where(Email.account_id == account_id)
    spam_q = select(func.count()).select_from(spam_base.subquery())
    spam_filtered = (await db.execute(spam_q)).scalar() or 0

    # Auto classification rate
    auto_base = (
        select(Email)
        .join(Classification, Classification.email_id == Email.id)
        .where(Email.date >= since)
    )
    if account_id:
        auto_base = auto_base.where(Email.account_id == account_id)
    classified_total = (
        await db.execute(select(func.count()).select_from(auto_base.subquery()))
    ).scalar() or 0

    auto_classified_base = auto_base.where(Email.processing_status == "auto_processed")
    auto_count = (
        await db.execute(select(func.count()).select_from(auto_classified_base.subquery()))
    ).scalar() or 0
    auto_rate = (auto_count / classified_total * 100) if classified_total > 0 else 0

    # Newsletters
    nl_base = select(Newsletter)
    if account_id:
        nl_base = nl_base.where(Newsletter.account_id == account_id)
    newsletters_tracked = (
        await db.execute(select(func.count()).select_from(nl_base.subquery()))
    ).scalar() or 0

    return AnalyticsOverview(
        period=period,
        emails_received=emails_received,
        emails_today=emails_today,
        review_pending=review_pending,
        phishing_blocked=phishing_blocked,
        spam_filtered=spam_filtered,
        auto_classification_rate=round(auto_rate, 1),
        newsletters_tracked=newsletters_tracked,
    )


# ---------------------------------------------------------------------------
# Categories breakdown
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=CategoriesResponse)
async def categories_breakdown(
    account_id: uuid.UUID | None = None,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get email count breakdown by category."""
    since = _period_start(period)

    query = (
        select(Classification.category, func.count().label("cnt"))
        .join(Email, Email.id == Classification.email_id)
        .where(Email.date >= since)
        .group_by(Classification.category)
        .order_by(func.count().desc())
    )
    if account_id:
        query = query.where(Email.account_id == account_id)

    result = await db.execute(query)
    rows = result.all()

    total = sum(r.cnt for r in rows)
    categories = [
        CategoryBreakdown(
            category=r.category or "unknown",
            count=r.cnt,
            percentage=round(r.cnt / total * 100, 1) if total > 0 else 0,
        )
        for r in rows
    ]

    return CategoriesResponse(period=period, total=total, categories=categories)


# ---------------------------------------------------------------------------
# Daily volume
# ---------------------------------------------------------------------------


@router.get("/volume", response_model=VolumeResponse)
async def daily_volume(
    account_id: uuid.UUID | None = None,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get daily email volume with category breakdown."""
    since = _period_start(period)

    query = (
        select(
            cast(Email.date, Date).label("day"),
            Classification.category,
            func.count().label("cnt"),
        )
        .outerjoin(Classification, Classification.email_id == Email.id)
        .where(Email.date >= since)
        .group_by("day", Classification.category)
        .order_by("day")
    )
    if account_id:
        query = query.where(Email.account_id == account_id)

    result = await db.execute(query)
    rows = result.all()

    # Group by day
    days_map: dict[str, DailyVolume] = {}
    for row in rows:
        day_str = str(row.day)
        if day_str not in days_map:
            days_map[day_str] = DailyVolume(date=day_str, total=0, by_category={})
        cat = row.category or "unknown"
        days_map[day_str].by_category[cat] = row.cnt
        days_map[day_str].total += row.cnt

    return VolumeResponse(
        period=period,
        days=sorted(days_map.values(), key=lambda d: d.date),
    )


# ---------------------------------------------------------------------------
# Top senders
# ---------------------------------------------------------------------------


@router.get("/top-senders", response_model=TopSendersResponse)
async def top_senders(
    account_id: uuid.UUID | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top senders by email volume."""
    query = select(SenderProfile).order_by(SenderProfile.total_emails.desc()).limit(limit)

    if account_id:
        query = query.where(SenderProfile.account_id == account_id)

    result = await db.execute(query)
    senders = result.scalars().all()

    return TopSendersResponse(
        limit=limit,
        senders=[
            TopSender(
                email_address=s.email_address,
                display_name=s.display_name,
                total_emails=s.total_emails,
                primary_category=s.primary_category,
                last_email_at=s.last_email_at.isoformat() if s.last_email_at else None,
            )
            for s in senders
        ],
    )
