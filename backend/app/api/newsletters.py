"""Newsletters — list, stats, unsubscribe."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.newsletter import Newsletter
from app.schemas.newsletter import (
    NewsletterResponse,
    NewsletterStatsResponse,
    UnsubscribeRequest,
    UnsubscribeResponse,
    UnsubscribeResult,
)
from app.services import newsletter_service

router = APIRouter()


@router.get("")
async def list_newsletters(
    account_id: uuid.UUID | None = None,
    subscription_status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Newsletter)
    if account_id:
        query = query.where(Newsletter.account_id == account_id)
    if subscription_status:
        query = query.where(Newsletter.subscription_status == subscription_status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Newsletter.total_received.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    items = [NewsletterResponse.model_validate(n) for n in result.scalars().all()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }


@router.get("/stats", response_model=NewsletterStatsResponse)
async def newsletter_stats(
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await newsletter_service.compute_newsletter_stats(db, account_id=account_id)


@router.post("/bulk-unsubscribe", response_model=UnsubscribeResponse)
async def bulk_unsubscribe(data: UnsubscribeRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    failed = 0
    results: list[UnsubscribeResult] = []

    for nl_id in data.newsletter_ids:
        result = await db.execute(select(Newsletter).where(Newsletter.id == nl_id))
        newsletter = result.scalar_one_or_none()
        if not newsletter:
            results.append(
                UnsubscribeResult(newsletter_id=nl_id, status="not_found")
            )
            failed += 1
            continue

        outcome = await newsletter_service.unsubscribe_newsletter(db, newsletter)
        results.append(
            UnsubscribeResult(
                newsletter_id=nl_id,
                status=outcome.get("status", "failed"),
                message=outcome.get("message"),
            )
        )
        if outcome.get("status") == "success":
            success += 1
        else:
            failed += 1

    return UnsubscribeResponse(success=success, failed=failed, results=results)


@router.post("/{newsletter_id}/unsubscribe")
async def unsubscribe_one(newsletter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Newsletter).where(Newsletter.id == newsletter_id))
    newsletter = result.scalar_one_or_none()
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter non trouvée")

    return await newsletter_service.unsubscribe_newsletter(db, newsletter)
