"""API routes for rule management."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.classification import Classification
from app.models.email import Email
from app.models.rule import Rule
from app.schemas.email import ClassificationSummary, EmailResponse
from app.schemas.rule import (
    RuleCreate,
    RuleResponse,
    RuleTestRequest,
    RuleTestResponse,
    RuleUpdate,
)
from app.services.classifier import get_llm_provider
from app.services.llm_service import interpret_rule
from app.services.rule_engine import (
    evaluate_structured_rule,
    get_matched_conditions_description,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all rules, ordered by priority DESC."""
    query = select(Rule).order_by(Rule.priority.desc())
    if account_id:
        query = query.where(
            (Rule.account_id == account_id) | (Rule.account_id == None)  # noqa: E711
        )

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(data: RuleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new rule."""
    # Validate type
    if data.type not in ("structured", "natural"):
        raise HTTPException(status_code=400, detail="Type doit être 'structured' ou 'natural'")

    if data.type == "structured" and not data.conditions:
        raise HTTPException(
            status_code=400, detail="Les règles structurées nécessitent des conditions"
        )

    if data.type == "natural" and not data.natural_text:
        raise HTTPException(status_code=400, detail="Les règles naturelles nécessitent un texte")

    rule = Rule(
        account_id=data.account_id,
        name=data.name,
        type=data.type,
        priority=data.priority,
        category=data.category,
        conditions=data.conditions,
        natural_text=data.natural_text,
        actions=data.actions,
    )
    db.add(rule)
    await db.flush()
    return rule


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get rule details."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")
    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: uuid.UUID, data: RuleUpdate, db: AsyncSession = Depends(get_db)):
    """Update a rule."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a rule."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")

    await db.delete(rule)


# ---------------------------------------------------------------------------
# Matched emails
# ---------------------------------------------------------------------------


@router.get("/{rule_id}/emails")
async def list_rule_emails(
    rule_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List emails matched by a specific rule (via classifications table)."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")

    # Query emails classified by this rule (via classification.rule_id)
    # Also include emails linked via actions table (for older data before migration)
    query = (
        select(Email)
        .join(Classification, Classification.email_id == Email.id)
        .where(Classification.rule_id == rule_id)
        .options(selectinload(Email.classification))
    )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort + paginate
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


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@router.post("/{rule_id}/test", response_model=RuleTestResponse)
async def test_rule(
    rule_id: uuid.UUID,
    data: RuleTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Test a rule against an existing email (without executing actions)."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Règle non trouvée")

    email_result = await db.execute(
        select(Email).options(selectinload(Email.classification)).where(Email.id == data.email_id)
    )
    email = email_result.scalar_one_or_none()
    if not email:
        raise HTTPException(status_code=404, detail="Email non trouvé")

    classification = email.classification

    if rule.type == "structured":
        matches = evaluate_structured_rule(rule, email, classification)
        matched_conds = get_matched_conditions_description(rule, email, classification)

        return RuleTestResponse(
            matches=matches,
            matched_conditions=matched_conds if matches else None,
            actions_preview=rule.actions if matches else None,
        )
    else:
        # Natural language rule: use LLM to interpret
        try:
            llm = await get_llm_provider(db)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"LLM non disponible pour tester la règle: {e}",
            )

        interpretation = await interpret_rule(
            llm,
            rule_text=rule.natural_text or "",
            from_name=email.from_name or "",
            from_address=email.from_address,
            subject=email.subject or "",
            category=classification.category if classification else "",
            date=str(email.date),
            body_excerpt=email.body_excerpt or "",
        )

        return RuleTestResponse(
            matches=interpretation.matches,
            reason=interpretation.reason or None,
            actions_preview=rule.actions if interpretation.matches else None,
        )
