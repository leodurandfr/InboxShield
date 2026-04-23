"""Email threads — list, detail, stats. Reply-tracking lives in Phase 3."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.email import Email, EmailThread
from app.schemas.email import ClassificationSummary, EmailResponse
from app.schemas.thread import ThreadResponse, ThreadStatsResponse

router = APIRouter()


@router.get("")
async def list_threads(
    account_id: uuid.UUID | None = None,
    filter: str | None = Query(None, pattern="^(all|awaiting_reply|awaiting_response)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailThread)
    if account_id:
        query = query.where(EmailThread.account_id == account_id)
    if filter == "awaiting_reply":
        query = query.where(EmailThread.awaiting_reply.is_(True))
    elif filter == "awaiting_response":
        query = query.where(EmailThread.awaiting_response.is_(True))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(EmailThread.last_email_at.desc().nullslast())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    items = [ThreadResponse.model_validate(t) for t in result.scalars().all()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }


@router.get("/stats", response_model=ThreadStatsResponse)
async def thread_stats(
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(EmailThread)
    if account_id:
        base = base.where(EmailThread.account_id == account_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    awaiting_reply = (
        await db.execute(
            select(func.count()).select_from(
                base.where(EmailThread.awaiting_reply.is_(True)).subquery()
            )
        )
    ).scalar() or 0

    awaiting_response = (
        await db.execute(
            select(func.count()).select_from(
                base.where(EmailThread.awaiting_response.is_(True)).subquery()
            )
        )
    ).scalar() or 0

    oldest = (
        await db.execute(
            base.where(
                (EmailThread.awaiting_reply.is_(True)) | (EmailThread.awaiting_response.is_(True))
            )
            .order_by(EmailThread.reply_needed_since.asc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()

    return ThreadStatsResponse(
        total=total,
        awaiting_reply=awaiting_reply,
        awaiting_response=awaiting_response,
        oldest_awaiting=oldest.reply_needed_since if oldest else None,
    )


@router.get("/{thread_id}")
async def get_thread(thread_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmailThread)
        .options(selectinload(EmailThread.emails).selectinload(Email.classification))
        .where(EmailThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouvé")

    emails: list[EmailResponse] = []
    for email in sorted(thread.emails, key=lambda e: e.date):
        item = EmailResponse.model_validate(email)
        if email.classification:
            item.classification = ClassificationSummary.model_validate(email.classification)
        emails.append(item)

    return {
        "thread": ThreadResponse.model_validate(thread),
        "emails": emails,
    }


@router.post("/{thread_id}/resolve")
async def resolve_thread(thread_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailThread).where(EmailThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouvé")
    thread.awaiting_reply = False
    thread.awaiting_response = False
    thread.reply_needed_since = None
    return {"status": "ok"}


@router.post("/{thread_id}/ignore")
async def ignore_thread(thread_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await resolve_thread(thread_id, db)  # same effect for now
