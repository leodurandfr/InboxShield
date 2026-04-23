"""API routes for email listing, filtering, and actions."""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.account import Account
from app.models.classification import Classification
from app.models.email import Email
from app.schemas.email import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionResult,
    EmailDetailResponse,
    EmailFlagRequest,
    EmailMoveRequest,
    EmailResponse,
)
from app.services.action_service import execute_actions
from app.services.classifier import reclassify_email

router = APIRouter()


# ---------------------------------------------------------------------------
# List / Detail
# ---------------------------------------------------------------------------


@router.get("")
async def list_emails(
    account_id: uuid.UUID | None = None,
    category: str | None = None,
    processing_status: str | None = None,
    is_read: bool | None = None,
    is_phishing: bool | None = None,
    classification_status: str | None = None,
    folder: str | None = None,
    from_address: str | None = None,
    subject: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "-date",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List emails with pagination and filters."""
    query = select(Email).options(selectinload(Email.classification))

    # Apply filters
    if account_id:
        query = query.where(Email.account_id == account_id)
    if processing_status:
        query = query.where(Email.processing_status == processing_status)
    if is_read is not None:
        query = query.where(Email.is_read == is_read)
    if folder:
        query = query.where(Email.folder == folder)
    if from_address:
        query = query.where(Email.from_address.ilike(f"%{from_address}%"))
    if subject:
        query = query.where(Email.subject.ilike(f"%{subject}%"))
    if date_from:
        query = query.where(Email.date >= date_from)
    if date_to:
        query = query.where(Email.date <= date_to)

    # Filter by classification fields (requires join)
    if category or is_phishing is not None or classification_status:
        query = query.join(Classification, Classification.email_id == Email.id, isouter=True)
        if category:
            query = query.where(Classification.category == category)
        if is_phishing is not None:
            query = query.where(Classification.is_phishing == is_phishing)
        if classification_status:
            query = query.where(Classification.status == classification_status)

    # Don't show archived emails by default
    query = query.where(Email.is_archived == False)  # noqa: E712

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    if sort == "-date":
        query = query.order_by(Email.date.desc())
    elif sort == "date":
        query = query.order_by(Email.date.asc())
    elif sort == "-created_at":
        query = query.order_by(Email.created_at.desc())
    elif sort == "created_at":
        query = query.order_by(Email.created_at.asc())
    elif sort == "from_address":
        query = query.order_by(Email.from_address.asc())
    else:
        query = query.order_by(Email.date.desc())

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    emails = result.scalars().unique().all()

    # Build response
    items = []
    for email in emails:
        item = EmailResponse.model_validate(email)
        if email.classification:
            from app.schemas.email import ClassificationSummary

            item.classification = ClassificationSummary.model_validate(email.classification)
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(email_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get email details with classification."""
    result = await db.execute(
        select(Email).options(selectinload(Email.classification)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if not email:
        raise HTTPException(status_code=404, detail="Email non trouvé")

    response = EmailDetailResponse.model_validate(email)
    if email.classification:
        from app.schemas.email import ClassificationSummary

        response.classification = ClassificationSummary.model_validate(email.classification)
    return response


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


async def _get_email_with_account(email_id: uuid.UUID, db: AsyncSession) -> tuple[Email, Account]:
    """Helper: get email + its account."""
    result = await db.execute(
        select(Email).options(selectinload(Email.account)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if not email:
        raise HTTPException(status_code=404, detail="Email non trouvé")
    return email, email.account


@router.post("/{email_id}/move")
async def move_email(
    email_id: uuid.UUID,
    data: EmailMoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Move an email to another IMAP folder."""
    email, account = await _get_email_with_account(email_id, db)

    results = await execute_actions(
        db,
        email=email,
        account_host=account.imap_host,
        account_port=account.imap_port,
        account_username=account.username,
        encrypted_password=account.encrypted_password,
        actions=[{"type": "move", "folder": data.folder}],
        trigger="manual",
    )

    if results and results[0]["status"] == "failed":
        raise HTTPException(status_code=500, detail=results[0].get("error", "Échec du déplacement"))

    return {"status": "ok", "folder": data.folder}


@router.post("/{email_id}/flag")
async def flag_email(
    email_id: uuid.UUID,
    data: EmailFlagRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set or toggle a flag on an email."""
    email, account = await _get_email_with_account(email_id, db)

    results = await execute_actions(
        db,
        email=email,
        account_host=account.imap_host,
        account_port=account.imap_port,
        account_username=account.username,
        encrypted_password=account.encrypted_password,
        actions=[{"type": "flag", "value": data.flag}],
        trigger="manual",
    )

    if results and results[0]["status"] == "failed":
        raise HTTPException(status_code=500, detail=results[0].get("error", "Échec du flag"))

    return {"status": "ok", "flag": data.flag}


@router.post("/{email_id}/reclassify")
async def reclassify(email_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Force re-classification of an email via LLM."""
    email, account = await _get_email_with_account(email_id, db)

    classification = await reclassify_email(db, email, account)

    if classification is None:
        raise HTTPException(status_code=500, detail="Re-classification échouée")

    return {
        "status": "ok",
        "classification": {
            "category": classification.category,
            "confidence": classification.confidence,
            "status": classification.status,
            "classified_by": classification.classified_by,
        },
    }


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_action(data: BulkActionRequest, db: AsyncSession = Depends(get_db)):
    """Execute an action on multiple emails."""
    results: list[BulkActionResult] = []
    success_count = 0
    failed_count = 0

    for eid in data.email_ids:
        try:
            email, account = await _get_email_with_account(eid, db)
            action_results = await execute_actions(
                db,
                email=email,
                account_host=account.imap_host,
                account_port=account.imap_port,
                account_username=account.username,
                encrypted_password=account.encrypted_password,
                actions=[data.action],
                trigger="manual_bulk",
            )

            if action_results and action_results[0]["status"] == "success":
                results.append(BulkActionResult(email_id=eid, status="success"))
                success_count += 1
            else:
                results.append(BulkActionResult(email_id=eid, status="failed"))
                failed_count += 1

        except HTTPException:
            results.append(BulkActionResult(email_id=eid, status="not_found"))
            failed_count += 1
        except Exception:
            results.append(BulkActionResult(email_id=eid, status="failed"))
            failed_count += 1

    return BulkActionResponse(success=success_count, failed=failed_count, results=results)
