"""Review queue — list, approve, correct."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.classification import Classification
from app.models.email import Email
from app.schemas.email import ClassificationSummary, EmailResponse
from app.schemas.review import (
    BulkApproveRequest,
    BulkApproveResponse,
    BulkApproveResult,
    ReviewCorrectRequest,
)
from app.services.classifier import approve_classification, correct_classification

router = APIRouter()


async def _get_email_with_context(
    email_id: uuid.UUID, db: AsyncSession
) -> tuple[Email, Classification]:
    result = await db.execute(
        select(Email)
        .options(
            selectinload(Email.classification),
            selectinload(Email.account),
        )
        .where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if not email:
        raise HTTPException(status_code=404, detail="Email non trouvé")
    if not email.classification:
        raise HTTPException(status_code=400, detail="Email non classifié")
    return email, email.classification


@router.get("")
async def list_review(
    account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List emails pending manual review (classification.status = 'review')."""
    query = (
        select(Email)
        .join(Classification, Classification.email_id == Email.id)
        .where(Classification.status == "review")
        .options(selectinload(Email.classification))
    )
    if account_id:
        query = query.where(Email.account_id == account_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Email.date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    emails = result.scalars().unique().all()

    items = []
    for email in emails:
        item = EmailResponse.model_validate(email)
        if email.classification:
            item.classification = ClassificationSummary.model_validate(email.classification)
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }


@router.post("/{email_id}/approve")
async def approve(email_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    email, classification = await _get_email_with_context(email_id, db)
    await approve_classification(db, classification, email, email.account)
    return {"status": "ok"}


@router.post("/{email_id}/correct")
async def correct(
    email_id: uuid.UUID,
    data: ReviewCorrectRequest,
    db: AsyncSession = Depends(get_db),
):
    email, classification = await _get_email_with_context(email_id, db)
    correction = await correct_classification(
        db,
        classification,
        email,
        email.account,
        corrected_category=data.corrected_category,
        user_note=data.user_note,
    )
    return {
        "status": "ok",
        "corrected_category": correction.corrected_category,
    }


@router.post("/bulk-approve", response_model=BulkApproveResponse)
async def bulk_approve(data: BulkApproveRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    failed = 0
    results: list[BulkApproveResult] = []

    for eid in data.email_ids:
        try:
            email, classification = await _get_email_with_context(eid, db)
            await approve_classification(db, classification, email, email.account)
            results.append(BulkApproveResult(email_id=eid, status="success"))
            success += 1
        except HTTPException:
            results.append(BulkApproveResult(email_id=eid, status="not_found"))
            failed += 1
        except Exception:
            results.append(BulkApproveResult(email_id=eid, status="failed"))
            failed += 1

    return BulkApproveResponse(success=success, failed=failed, results=results)
