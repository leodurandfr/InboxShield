"""Sender profiles — list, detail, block/unblock."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.sender_profile import SenderProfile
from app.schemas.sender import (
    CategoryStatEntry,
    SenderBlockRequest,
    SenderDetailResponse,
    SenderResponse,
)
from app.services import sender_service

router = APIRouter()


@router.get("")
async def list_senders(
    account_id: uuid.UUID | None = None,
    filter: str | None = Query(None, pattern="^(all|newsletters|blocked)$"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(SenderProfile)
    if account_id:
        query = query.where(SenderProfile.account_id == account_id)
    if filter == "newsletters":
        query = query.where(SenderProfile.is_newsletter.is_(True))
    elif filter == "blocked":
        query = query.where(SenderProfile.is_blocked.is_(True))
    if search:
        like = f"%{search}%"
        query = query.where(
            (SenderProfile.email_address.ilike(like)) | (SenderProfile.display_name.ilike(like))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(SenderProfile.total_emails.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    items = [SenderResponse.model_validate(s) for s in result.scalars().all()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }


@router.get("/{sender_id}", response_model=SenderDetailResponse)
async def get_sender(sender_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SenderProfile)
        .options(selectinload(SenderProfile.category_stats))
        .where(SenderProfile.id == sender_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Expéditeur non trouvé")

    response = SenderDetailResponse.model_validate(profile)
    response.category_stats = [
        CategoryStatEntry(
            category=s.category,
            count=s.count,
            corrected_count=s.corrected_count,
        )
        for s in (profile.category_stats or [])
    ]
    return response


@router.put("/{sender_id}/block", response_model=SenderResponse)
async def set_sender_block(
    sender_id: uuid.UUID,
    data: SenderBlockRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SenderProfile).where(SenderProfile.id == sender_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Expéditeur non trouvé")

    if data.is_blocked:
        await sender_service.block_sender(db, profile.account_id, profile.email_address)
    else:
        await sender_service.unblock_sender(db, profile.account_id, profile.email_address)
    await db.refresh(profile)
    return profile
