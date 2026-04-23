"""API routes for system health, stats, and maintenance."""

import random
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.account import Account
from app.models.classification import Classification
from app.models.email import Email
from app.schemas.system import (
    HealthResponse,
    IMAPAccountCheck,
    LLMStatus,
    LoadedModel,
    OllamaManagerStatus,
    SchedulerInfo,
    ServiceCheck,
    SystemStats,
)
from app.services.classifier import classify_single_email, get_llm_provider, get_settings
from app.services.ollama_manager import ollama_manager
from app.services.scheduler import (
    adjust_confidence_threshold,
    cancel_all_analysis,
    cleanup_old_data,
    get_scheduler_info,
    poll_all_accounts_manual,
    reanalyze_all_emails,
)

router = APIRouter()

# Track startup time for uptime calculation
_start_time = time.monotonic()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check: DB + LLM + IMAP accounts + scheduler."""
    checks: dict = {}

    # Database check
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency = int((time.monotonic() - start) * 1000)
        checks["database"] = ServiceCheck(status="ok", latency_ms=latency)
    except Exception as e:
        checks["database"] = ServiceCheck(status="error", error=str(e))

    # LLM check
    try:
        from app.services.classifier import get_llm_provider

        llm = await get_llm_provider(db)
        start = time.monotonic()
        available = await llm.is_available()
        latency = int((time.monotonic() - start) * 1000)

        if available:
            checks["ollama"] = ServiceCheck(status="ok", latency_ms=latency)
        else:
            checks["ollama"] = ServiceCheck(status="error", error="LLM non disponible")
    except Exception as e:
        checks["ollama"] = ServiceCheck(status="error", error=str(e))

    # IMAP accounts check
    imap_accounts: list[IMAPAccountCheck] = []
    result = await db.execute(
        select(Account).where(Account.is_active == True)  # noqa: E712
    )
    for account in result.scalars().all():
        imap_accounts.append(
            IMAPAccountCheck(
                account=account.email,
                status="ok" if not account.last_poll_error else "error",
                last_poll=account.last_poll_at,
                error=account.last_poll_error,
            )
        )

    # Scheduler info
    sched_info = get_scheduler_info()
    next_poll = None
    for job in sched_info.get("jobs", []):
        if job["id"] == "poll_emails" and job["next_run"]:
            next_poll = job["next_run"]
            break

    scheduler_status = SchedulerInfo(
        running=sched_info["running"],
        jobs=len(sched_info["jobs"]),
        next_poll=next_poll,
    )

    # Overall status
    overall = "healthy"
    if checks.get("database", {}) and getattr(checks.get("database"), "status", "") == "error":
        overall = "unhealthy"
    elif checks.get("ollama", {}) and getattr(checks.get("ollama"), "status", "") == "error":
        overall = "degraded"

    # Ollama manager status (lightweight — no disk/ps probes for the health endpoint)
    om_status = ollama_manager.get_status()
    ollama_mgr = OllamaManagerStatus(
        running=om_status["running"],
        managed_by_us=om_status["managed_by_us"],
        pid=om_status["pid"],
        binary_path=om_status["binary_path"],
        install_method=om_status.get("install_method"),
        service_status=om_status.get("service_status"),
    )

    return HealthResponse(
        status=overall,
        checks={k: v.model_dump() for k, v in checks.items()},
        imap_accounts=imap_accounts,
        scheduler=scheduler_status,
        ollama_manager=ollama_mgr,
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=SystemStats)
async def stats(db: AsyncSession = Depends(get_db)):
    """System statistics."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Uptime
    uptime = int(time.monotonic() - _start_time)

    # Emails processed today
    emails_today = (
        await db.execute(
            select(func.count()).select_from(Email).where(Email.created_at >= today_start)
        )
    ).scalar() or 0

    # Classifications today
    classifications_today = (
        await db.execute(
            select(func.count())
            .select_from(Classification)
            .where(Classification.created_at >= today_start)
        )
    ).scalar() or 0

    # Pending review
    pending_review = (
        await db.execute(
            select(func.count())
            .select_from(Classification)
            .where(Classification.status == "review")
        )
    ).scalar() or 0

    # Active accounts
    active_accounts = (
        await db.execute(
            select(func.count()).select_from(Account).where(Account.is_active == True)  # noqa: E712
        )
    ).scalar() or 0

    # LLM status
    llm_status = LLMStatus(configured=False, available=False, provider="", model="")
    try:
        app_settings = await get_settings(db)
        llm_status.provider = app_settings.llm_provider or ""
        llm_status.model = app_settings.llm_model or ""
        llm_status.configured = bool(app_settings.llm_provider and app_settings.llm_model)

        if app_settings.llm_provider == "ollama":
            try:
                llm = await get_llm_provider(db)
                llm_status.available = await llm.is_available()
                if not llm_status.available:
                    llm_status.error = "Ollama non disponible ou modèle non installé"
            except Exception:
                llm_status.error = "Ollama non disponible"
        elif app_settings.llm_provider in ("anthropic", "openai", "mistral"):
            if not app_settings.llm_api_key_encrypted:
                llm_status.error = f"Clé API non configurée pour {app_settings.llm_provider}"
            else:
                llm_status.available = True
    except Exception as e:
        llm_status.error = str(e)

    return SystemStats(
        uptime_seconds=uptime,
        emails_processed_today=emails_today,
        classifications_today=classifications_today,
        pending_review=pending_review,
        active_accounts=active_accounts,
        llm_status=llm_status,
    )


# ---------------------------------------------------------------------------
# Manual poll (all accounts)
# ---------------------------------------------------------------------------


@router.post("/poll-all")
async def poll_all(db: AsyncSession = Depends(get_db)):
    """Trigger an immediate email fetch + classification for all active accounts."""
    # Check LLM availability to inform the user
    llm_available = False
    llm_warning: str | None = None
    try:
        llm = await get_llm_provider(db)
        llm_available = await llm.is_available()
        if not llm_available:
            llm_warning = "LLM non disponible — les emails seront envoyés en file de révision"
    except Exception as e:
        llm_warning = f"LLM non configuré : {e}"

    # Broadcast poll started event
    from app.services.ws_manager import ws_manager

    await ws_manager.broadcast("poll_started", {})

    result = await poll_all_accounts_manual()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    result["llm_available"] = llm_available
    if llm_warning:
        result["llm_warning"] = llm_warning
    return result


# ---------------------------------------------------------------------------
# Reanalyze all emails
# ---------------------------------------------------------------------------


@router.post("/reanalyze-all")
async def reanalyze_all(db: AsyncSession = Depends(get_db)):
    """Wipe all emails and re-fetch from IMAP since initial_fetch_since date."""
    # Check LLM availability
    llm_available = False
    llm_warning: str | None = None
    try:
        llm = await get_llm_provider(db)
        llm_available = await llm.is_available()
        if not llm_available:
            llm_warning = "LLM non disponible — les emails seront envoyés en file de révision"
    except Exception as e:
        llm_warning = f"LLM non configuré : {e}"

    from app.services.ws_manager import ws_manager

    await ws_manager.broadcast("poll_started", {})

    result = await reanalyze_all_emails()
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    result["llm_available"] = llm_available
    if llm_warning:
        result["llm_warning"] = llm_warning
    return result


@router.post("/cancel-analysis")
async def cancel_analysis():
    """Cancel all running background classification tasks."""
    result = await cancel_all_analysis()
    return result


# ---------------------------------------------------------------------------
# Test email (dev/debug)
# ---------------------------------------------------------------------------


class TestEmailRequest(BaseModel):
    from_address: str = "test@example.com"
    from_name: str | None = "Test Sender"
    subject: str | None = "Test email"
    body: str | None = "This is a test email for classification debugging."
    account_id: str | None = None  # If None, use the first active account


@router.post("/test-email")
async def create_test_email(payload: TestEmailRequest, db: AsyncSession = Depends(get_db)):
    """Create a fake email and classify it immediately (dev/debug tool)."""
    # Find an account to attach the email to
    if payload.account_id:
        import uuid as _uuid

        result = await db.execute(
            select(Account).where(Account.id == _uuid.UUID(payload.account_id))
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Compte introuvable")
    else:
        result = await db.execute(
            select(Account).where(Account.is_active == True).limit(1)  # noqa: E712
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=400, detail="Aucun compte actif configuré")

    # Generate a unique negative UID to avoid collision with real IMAP UIDs
    test_uid = -random.randint(1, 2_000_000_000)

    email = Email(
        account_id=account.id,
        uid=test_uid,
        message_id=f"<test-{abs(test_uid)}@inboxshield.local>",
        from_address=payload.from_address,
        from_name=payload.from_name,
        subject=payload.subject,
        body_excerpt=payload.body,
        date=datetime.now(UTC),
        folder="INBOX",
        is_read=False,
        is_flagged=False,
        has_attachments=False,
        processing_status="pending",
    )
    db.add(email)
    await db.flush()
    await db.refresh(email)

    # Classify immediately
    settings = await get_settings(db)
    try:
        llm = await get_llm_provider(db)
    except Exception:
        llm = None

    classification = await classify_single_email(db, email, account, settings, llm)
    await db.commit()

    return {
        "status": "ok",
        "email_id": str(email.id),
        "classification": {
            "category": classification.category if classification else None,
            "confidence": classification.confidence if classification else None,
            "status": classification.status if classification else None,
            "classified_by": classification.classified_by if classification else None,
        }
        if classification
        else None,
    }


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


@router.post("/cleanup")
async def trigger_cleanup():
    """Manually trigger data cleanup (retention policy)."""
    try:
        await cleanup_old_data()
        return {"status": "ok", "message": "Nettoyage terminé"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Threshold adjustment
# ---------------------------------------------------------------------------


@router.post("/adjust-threshold")
async def trigger_threshold_adjustment():
    """Manually trigger confidence threshold evaluation and adjustment."""
    try:
        result = await adjust_confidence_threshold()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Ollama manager
# ---------------------------------------------------------------------------


@router.get("/ollama/status", response_model=OllamaManagerStatus)
async def ollama_status():
    """Rich Ollama status: install method, loaded models, disk usage."""
    status = ollama_manager.get_status()
    loaded_raw: list[dict] = []
    installed: list[dict] = []
    disk = {"total_bytes": 0, "model_count": 0}
    if status["running"]:
        loaded_raw = await ollama_manager.get_loaded_models()
        installed = await ollama_manager.list_installed_models()
        disk = await ollama_manager.get_disk_usage()

    return OllamaManagerStatus(
        running=status["running"],
        managed_by_us=status["managed_by_us"],
        pid=status["pid"],
        binary_path=status["binary_path"],
        install_method=status.get("install_method"),
        service_status=status.get("service_status"),
        loaded_models=[LoadedModel(**m) for m in loaded_raw],
        installed_models=installed,
        total_disk_bytes=int(disk.get("total_bytes") or 0),
    )


@router.post("/ollama/unload/{model_name:path}")
async def ollama_unload(model_name: str):
    """Force-unload a model from RAM (non-destructive — doesn't uninstall)."""
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name requis")
    ok = await ollama_manager.unload_model(model_name)
    if not ok:
        raise HTTPException(status_code=502, detail="Ollama a refusé la demande de déchargement")
    return {"status": "ok", "model": model_name}


@router.post("/ollama/restart")
async def ollama_restart():
    """Restart Ollama via the manager."""
    await ollama_manager.restart()
    status = ollama_manager.get_status()
    return {
        "status": "ok" if status["running"] else "error",
        "running": status["running"],
        "managed_by_us": status["managed_by_us"],
    }
