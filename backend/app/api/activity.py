"""Activity feed — list recent activity log entries."""

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.activity_log import ActivityLog
from app.schemas.activity import ActivityLogResponse

router = APIRouter()


@router.get("")
async def list_activity(
    account_id: uuid.UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(ActivityLog)
    if account_id:
        query = query.where(ActivityLog.account_id == account_id)
    if event_type:
        query = query.where(ActivityLog.event_type == event_type)
    if severity:
        query = query.where(ActivityLog.severity == severity)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(ActivityLog.created_at.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    items = [ActivityLogResponse.model_validate(r) for r in result.scalars().all()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 0,
    }
