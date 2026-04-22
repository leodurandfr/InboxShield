"""Activity logging service for the dashboard feed."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog


async def log_activity(
    db: AsyncSession,
    event_type: str,
    title: str,
    severity: str = "info",
    account_id: uuid.UUID | None = None,
    email_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> ActivityLog:
    """Create an activity log entry."""
    log = ActivityLog(
        account_id=account_id,
        event_type=event_type,
        severity=severity,
        title=title,
        details=details,
        email_id=email_id,
    )
    db.add(log)
    return log


# Convenience functions for common events

async def log_email_classified(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    from_address: str,
    category: str,
    classified_by: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="email_classified",
        title=f"Email de {from_address} classé \u00ab {category} \u00bb ({classified_by})",
        account_id=account_id,
        email_id=email_id,
        details={"category": category, "classified_by": classified_by, "from_address": from_address},
    )


async def log_email_moved(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    from_address: str,
    folder: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="email_moved",
        title=f"Email de {from_address} \u2192 {folder}",
        account_id=account_id,
        email_id=email_id,
        details={"folder": folder, "from_address": from_address},
    )


async def log_phishing_detected(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    subject: str,
    from_address: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="phishing_detected",
        title=f"Phishing d\u00e9tect\u00e9 \u2014 \u00ab {subject} \u00bb de {from_address}",
        severity="warning",
        account_id=account_id,
        email_id=email_id,
        details={"subject": subject, "from_address": from_address},
    )


async def log_spam_detected(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    from_address: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="spam_detected",
        title=f"Spam filtr\u00e9 de {from_address}",
        account_id=account_id,
        email_id=email_id,
        details={"from_address": from_address},
    )


async def log_review_approved(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    from_address: str,
    category: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="review_approved",
        title=f"Review approuv\u00e9e \u2014 {from_address} \u2192 {category}",
        severity="success",
        account_id=account_id,
        email_id=email_id,
        details={"category": category, "from_address": from_address},
    )


async def log_review_corrected(
    db: AsyncSession,
    account_id: uuid.UUID,
    email_id: uuid.UUID,
    from_address: str,
    original_category: str,
    corrected_category: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="review_corrected",
        title=f"Classification corrig\u00e9e \u2014 {from_address} : {original_category} \u2192 {corrected_category}",
        severity="success",
        account_id=account_id,
        email_id=email_id,
        details={"original": original_category, "corrected": corrected_category},
    )


async def log_poll_error(
    db: AsyncSession,
    account_id: uuid.UUID,
    error: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="poll_error",
        title=f"Erreur de polling \u2014 {error[:100]}",
        severity="error",
        account_id=account_id,
        details={"error": error},
    )


async def log_llm_error(
    db: AsyncSession,
    account_id: uuid.UUID | None,
    error: str,
) -> ActivityLog:
    return await log_activity(
        db,
        event_type="llm_error",
        title=f"Erreur LLM \u2014 {error[:100]}",
        severity="error",
        account_id=account_id,
        details={"error": error},
    )
