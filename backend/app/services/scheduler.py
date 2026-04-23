"""APScheduler-based job scheduler integrated into FastAPI lifespan.

Jobs:
- poll_emails: Fetch new emails from all active accounts and classify them
- check_imap_health: Verify IMAP connectivity for all accounts
- cleanup_old_data: Purge old activity logs and archived emails
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, func, select, update

from app.db.database import async_session
from app.models.account import Account
from app.models.activity_log import ActivityLog
from app.models.email import Email, EmailThread
from app.models.settings import Settings
from app.services import activity_service, imap_service
from app.services.classifier import classify_batch, get_settings
from app.services.content_extraction import make_extraction_config
from app.services.encryption import decrypt
from app.services.thread_service import resolve_or_create_thread, update_thread_reply_status

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()

# Track background classification tasks to prevent GC
_background_tasks: set[asyncio.Task] = set()

# Cooperative cancellation flag — checked between batches
_cancel_requested = False


# ---------------------------------------------------------------------------
# Scheduler lifecycle (called from FastAPI lifespan)
# ---------------------------------------------------------------------------


async def start_scheduler() -> None:
    """Start the APScheduler with configured jobs."""
    async with async_session() as db:
        settings = await get_settings(db)
        interval = settings.polling_interval_minutes

    # Poll emails job
    scheduler.add_job(
        poll_all_accounts,
        "interval",
        minutes=interval,
        id="poll_emails",
        name="Poll emails from IMAP",
        replace_existing=True,
        max_instances=1,  # Don't overlap if a poll takes too long
    )

    # IMAP health check
    scheduler.add_job(
        check_imap_health,
        "interval",
        minutes=5,
        id="check_imap_health",
        name="Check IMAP connectivity",
        replace_existing=True,
        max_instances=1,
    )

    # Daily cleanup
    scheduler.add_job(
        cleanup_old_data,
        "cron",
        hour=3,
        minute=0,
        id="cleanup_old_data",
        name="Cleanup old logs and data",
        replace_existing=True,
    )

    # Daily threshold adjustment (evaluate and adjust confidence threshold)
    scheduler.add_job(
        adjust_confidence_threshold,
        "cron",
        hour=4,
        minute=0,
        id="adjust_threshold",
        name="Adjust confidence threshold",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started (poll interval: %d min)", interval)


async def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def update_poll_interval(minutes: int) -> None:
    """Update the polling interval at runtime."""
    if scheduler.running:
        scheduler.reschedule_job(
            "poll_emails",
            trigger="interval",
            minutes=minutes,
        )
        logger.info("Poll interval updated to %d minutes", minutes)


def get_scheduler_info() -> dict:
    """Get scheduler status info for the health endpoint."""
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
            )

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


# ---------------------------------------------------------------------------
# Job: Poll all accounts
# ---------------------------------------------------------------------------


async def poll_all_accounts() -> None:
    """Poll new emails from all active IMAP accounts and classify them."""
    logger.info("Starting email poll for all accounts...")

    async with async_session() as db:
        # Get all active accounts
        result = await db.execute(
            select(Account).where(Account.is_active == True)  # noqa: E712
        )
        accounts = result.scalars().all()

        if not accounts:
            logger.debug("No active accounts to poll")
            return

        for account in accounts:
            try:
                # Phase 1: fetch + save (commits immediately)
                email_ids = await _fetch_and_save_emails(db, account)

                # Phase 1b: pick up stale pending/failed/classifying emails
                # "pending"/"failed" stuck > 5 min, "classifying" stuck > 10 min
                stale_cutoff = datetime.now(UTC) - timedelta(minutes=5)
                classifying_cutoff = datetime.now(UTC) - timedelta(minutes=10)
                stale_result = await db.execute(
                    select(Email.id).where(
                        Email.account_id == account.id,
                        (
                            (
                                Email.processing_status.in_(["pending", "failed"])
                                & (Email.created_at < stale_cutoff)
                            )
                            | (Email.processing_status == "classifying")
                            & (Email.created_at < classifying_cutoff)
                        ),
                        Email.id.notin_(email_ids) if email_ids else True,
                    )
                )
                stale_ids = [row[0] for row in stale_result.all()]
                if stale_ids:
                    logger.info(
                        "Account %s: retrying %d stale pending/failed emails",
                        account.email,
                        len(stale_ids),
                    )
                    email_ids = email_ids + stale_ids

                # Phase 2: classify (waits for completion in scheduled job)
                if email_ids:
                    stats = await _classify_email_ids(db, email_ids, account.id)
                    logger.info(
                        "Account %s: %d classified, %d skipped, %d failed, %d review",
                        account.email,
                        stats["classified"],
                        stats["skipped"],
                        stats["failed"],
                        stats["review"],
                    )
            except Exception as e:
                await db.rollback()
                logger.exception("Poll failed for account %s", account.email)
                # Log the error in a new transaction
                try:
                    async with async_session() as error_db:
                        await activity_service.log_poll_error(error_db, account.id, str(e))
                        account_stmt = select(Account).where(Account.id == account.id)
                        acct = (await error_db.execute(account_stmt)).scalar_one()
                        acct.last_poll_error = str(e)[:500]
                        await error_db.commit()
                except Exception:
                    logger.exception("Failed to log poll error for %s", account.email)


def _get_folders_to_scan(account: Account) -> list[str]:
    """Return list of IMAP folders to scan for an account.

    For initial poll: inbox + spam/junk (to classify everything).
    For incremental poll: inbox only.
    """
    mapping = account.folder_mapping or {}
    inbox = mapping.get("inbox", "INBOX")

    if account.last_uid == 0:
        # Initial poll: scan all important folders
        folders = [inbox]
        for role in ("spam", "trash"):
            folder = mapping.get(role)
            if folder and folder not in folders:
                folders.append(folder)
        return folders

    return [inbox]


async def _save_fetched_to_db(
    db,
    account: Account,
    fetched: list,
    log_label: str = "",
) -> list:
    """Deduplicate, save emails to DB, assign threads, and commit.

    Shared logic for both incremental poll and full scan.
    Returns list of new email IDs.
    """
    if not fetched:
        account.last_poll_at = datetime.now(UTC)
        account.last_poll_error = None
        await db.commit()
        return []

    logger.info("Fetched %d emails for %s%s", len(fetched), account.email, log_label)

    new_emails: list[Email] = []
    max_uid = account.last_uid

    for raw in fetched:
        # Check for duplicate (uid + folder already exists for this account)
        existing = await db.execute(
            select(Email.id).where(
                Email.account_id == account.id,
                Email.uid == raw.uid,
                Email.folder == raw.folder,
            )
        )
        if existing.scalar_one_or_none():
            continue

        email = Email(
            account_id=account.id,
            uid=raw.uid,
            message_id=raw.message_id,
            in_reply_to=raw.in_reply_to,
            references=raw.references,
            from_address=raw.from_address,
            from_name=raw.from_name,
            reply_to=getattr(raw, "reply_to", None),
            to_addresses=raw.to_addresses,
            cc_addresses=raw.cc_addresses,
            subject=raw.subject,
            body_excerpt=raw.body_excerpt,
            body_html_excerpt=raw.body_html_excerpt,
            has_attachments=raw.has_attachments,
            attachment_names=raw.attachment_names,
            date=raw.date,
            folder=raw.folder,
            original_folder=raw.folder,
            is_read=raw.is_read,
            is_flagged=raw.is_flagged,
            size_bytes=raw.size_bytes,
            processing_status="pending",
        )
        db.add(email)
        new_emails.append(email)

        if raw.uid > max_uid:
            max_uid = raw.uid

    # Flush to get email IDs
    await db.flush()

    # Assign threads to new emails
    for email in new_emails:
        try:
            thread_id = await resolve_or_create_thread(
                db,
                account_id=account.id,
                message_id=email.message_id,
                in_reply_to=email.in_reply_to,
                references=email.references,
                subject=email.subject,
                from_address=email.from_address,
                to_addresses=email.to_addresses,
                email_date=email.date,
            )
            if thread_id:
                email.thread_id = thread_id
                await update_thread_reply_status(
                    db,
                    thread_id=thread_id,
                    from_address=email.from_address,
                    to_addresses=email.to_addresses,
                    user_email=account.email,
                    email_date=email.date,
                )
        except Exception:
            logger.exception("Thread assignment failed for email %s", email.id)

    # Update account polling state
    account.last_uid = max_uid
    account.last_poll_at = datetime.now(UTC)
    account.last_poll_error = None

    # Commit immediately so emails are visible in the UI
    new_email_ids = [e.id for e in new_emails]
    await db.commit()
    logger.info("Saved %d emails for %s%s", len(new_emails), account.email, log_label)

    return new_email_ids


async def _load_app_settings(db):
    """Load app settings (returns None if no settings row)."""
    result = await db.execute(select(Settings).where(Settings.id == 1))
    return result.scalar_one_or_none()


async def _fetch_and_save_emails(db, account: Account) -> list:
    """Fetch new emails from IMAP and save to DB. Returns list of new email IDs.

    This commits emails immediately so they're visible in the UI right away.
    """
    password = decrypt(account.encrypted_password)
    folders = _get_folders_to_scan(account)

    # Build extraction config from Settings.body_excerpt_length
    app_settings = await _load_app_settings(db)
    extraction_config = make_extraction_config(
        app_settings.body_excerpt_length if app_settings else 3000
    )

    fetched: list = []

    if account.last_uid == 0:
        since_date = app_settings.initial_fetch_since if app_settings else None
        logger.info(
            "Initial poll for %s — fetching all emails since %s from %s",
            account.email,
            since_date or "1st of month (default)",
            folders,
        )
        for folder in folders:
            try:
                folder_emails = await asyncio.to_thread(
                    imap_service.fetch_emails_since,
                    host=account.imap_host,
                    port=account.imap_port,
                    username=account.username,
                    password=password,
                    folder=folder,
                    since_date=since_date,
                    config=extraction_config,
                )
                fetched.extend(folder_emails)
            except Exception:
                logger.exception("Failed to fetch from folder %s for %s", folder, account.email)
    else:
        # Incremental poll: fetch new emails since last known UID (inbox only)
        inbox_folder = folders[0]
        fetched = await asyncio.to_thread(
            imap_service.fetch_new_emails,
            host=account.imap_host,
            port=account.imap_port,
            username=account.username,
            password=password,
            folder=inbox_folder,
            since_uid=account.last_uid,
            config=extraction_config,
        )

    return await _save_fetched_to_db(db, account, fetched)


async def _fetch_and_save_emails_full(db, account: Account) -> list:
    """Fetch emails using date-based criteria (comprehensive scan).

    Always scans all folders from the configured start date, regardless of last_uid.
    Used by manual poll to ensure all emails are captured. Deduplication prevents
    re-inserting emails already in the DB.
    """
    password = decrypt(account.encrypted_password)
    folders = _get_folders_to_scan(account)

    # For manual poll, always scan all folders (not just inbox)
    mapping = account.folder_mapping or {}
    inbox = mapping.get("inbox", "INBOX")
    if inbox not in folders:
        folders.insert(0, inbox)
    for role in ("spam", "trash"):
        folder = mapping.get(role)
        if folder and folder not in folders:
            folders.append(folder)

    # Read configured start date + body_excerpt_length from settings
    app_settings = await _load_app_settings(db)
    since_date = app_settings.initial_fetch_since if app_settings else None
    extraction_config = make_extraction_config(
        app_settings.body_excerpt_length if app_settings else 3000
    )

    logger.info(
        "Manual full scan for %s — fetching all emails since %s from %s",
        account.email,
        since_date or "1st of month (default)",
        folders,
    )

    fetched: list = []
    for folder in folders:
        try:
            folder_emails = await asyncio.to_thread(
                imap_service.fetch_emails_since,
                host=account.imap_host,
                port=account.imap_port,
                username=account.username,
                password=password,
                folder=folder,
                since_date=since_date,
                config=extraction_config,
            )
            fetched.extend(folder_emails)
        except Exception:
            logger.exception("Failed to fetch from folder %s for %s", folder, account.email)

    new_email_ids = await _save_fetched_to_db(
        db,
        account,
        fetched,
        log_label=" (full scan)",
    )

    # Broadcast real-time event
    from app.services.ws_manager import ws_manager

    if new_email_ids:
        await ws_manager.broadcast(
            "poll_complete",
            {
                "account_id": str(account.id),
                "account_email": account.email,
                "new_emails": len(new_email_ids),
            },
        )

    return new_email_ids


async def _classify_email_ids(db, email_ids: list, account_id) -> dict:
    """Classify a list of emails by their IDs. Returns stats dict."""
    email_result = await db.execute(select(Email).where(Email.id.in_(email_ids)))
    emails_to_classify = list(email_result.scalars().all())

    acct_result = await db.execute(select(Account).where(Account.id == account_id))
    account = acct_result.scalar_one()

    stats = await classify_batch(db, emails_to_classify, account)
    await db.commit()
    return stats


# ---------------------------------------------------------------------------
# Job: Poll a specific account (for manual trigger via API)
# ---------------------------------------------------------------------------


async def _classify_emails_background(email_ids: list, account_id) -> None:
    """Classify emails in the background (fire-and-forget).

    Processes in small batches and commits after each batch so results
    become visible in the UI progressively.  Checks ``_cancel_requested``
    between batches for cooperative cancellation.
    """
    global _cancel_requested
    batch_size = 10
    total_stats = {"total": len(email_ids), "classified": 0, "skipped": 0, "failed": 0, "review": 0}
    from app.services.ws_manager import ws_manager

    try:
        for i in range(0, len(email_ids), batch_size):
            # --- cooperative cancellation check ---
            if _cancel_requested:
                remaining = len(email_ids) - i
                logger.info(
                    "Classification cancelled for account %s (%d/%d processed, %d remaining)",
                    account_id,
                    i,
                    len(email_ids),
                    remaining,
                )
                return

            batch_ids = email_ids[i : i + batch_size]
            try:
                async with async_session() as db:
                    stats = await _classify_email_ids(db, batch_ids, account_id)
                    for key in ("classified", "skipped", "failed", "review"):
                        total_stats[key] += stats[key]
                    logger.info(
                        "Classified batch %d-%d/%d for account %s",
                        i + 1,
                        min(i + batch_size, len(email_ids)),
                        len(email_ids),
                        account_id,
                    )
                    # Broadcast progress
                    await ws_manager.broadcast(
                        "classification_progress",
                        {
                            "account_id": str(account_id),
                            "processed": min(i + batch_size, len(email_ids)),
                            "total": len(email_ids),
                            "batch_stats": stats,
                        },
                    )
            except Exception:
                total_stats["failed"] += len(batch_ids)
                logger.exception("Batch %d-%d classification failed", i + 1, i + batch_size)

        logger.info(
            "Background classification complete for account %s: "
            "%d classified, %d skipped, %d failed, %d review",
            account_id,
            total_stats["classified"],
            total_stats["skipped"],
            total_stats["failed"],
            total_stats["review"],
        )
        # Broadcast completion
        await ws_manager.broadcast(
            "classification_complete",
            {
                "account_id": str(account_id),
                "stats": total_stats,
            },
        )
    except Exception:
        logger.exception("Background classification failed for account %s", account_id)


async def poll_all_accounts_manual() -> dict:
    """Poll all active accounts (triggered manually from API).

    Always uses date-based fetching (comprehensive scan from configured date)
    with deduplication, so it picks up any emails missed by incremental polling.
    Scheduled polls remain incremental for efficiency.
    """
    async with async_session() as db:
        result = await db.execute(
            select(Account).where(Account.is_active == True)  # noqa: E712
        )
        accounts = result.scalars().all()

        if not accounts:
            return {"status": "ok", "accounts": [], "total_new_emails": 0}

        results = []
        total_new = 0

        for account in accounts:
            try:
                email_ids = await _fetch_and_save_emails_full(db, account)

                # Also pick up existing pending/failed/classifying emails for this account
                pending_result = await db.execute(
                    select(Email.id).where(
                        Email.account_id == account.id,
                        Email.processing_status.in_(["pending", "failed", "classifying"]),
                        Email.id.notin_(email_ids) if email_ids else True,
                    )
                )
                pending_ids = [row[0] for row in pending_result.all()]

                all_ids_to_classify = email_ids + pending_ids
                if all_ids_to_classify:
                    task = asyncio.create_task(
                        _classify_emails_background(all_ids_to_classify, account.id)
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

                results.append(
                    {
                        "account": account.email,
                        "new_emails": len(email_ids),
                        "pending_reclassified": len(pending_ids),
                    }
                )
                total_new += len(email_ids)
            except Exception as e:
                await db.rollback()
                logger.exception("Manual poll failed for account %s", account.email)
                results.append(
                    {
                        "account": account.email,
                        "error": str(e),
                    }
                )

        return {"status": "ok", "accounts": results, "total_new_emails": total_new}


async def reanalyze_all_emails() -> dict:
    """Wipe all emails and re-fetch from IMAP since the configured initial_fetch_since date.

    Steps:
    1. Cancel any running background classification tasks
    2. Delete all emails (cascades to classifications, urls, actions, corrections)
    3. Delete all email threads
    4. Reset account last_uid to 0 (forces full re-fetch)
    5. Re-fetch emails from IMAP using initial_fetch_since date
    6. Kick off background classification
    """
    # Cancel running classification tasks first
    await cancel_all_analysis()

    async with async_session() as db:
        # Get all active accounts
        accounts_result = await db.execute(
            select(Account).where(Account.is_active == True)  # noqa: E712
        )
        accounts = accounts_result.scalars().all()

        if not accounts:
            return {"status": "ok", "total_fetched": 0}

        # Delete all emails (CASCADE handles classifications, urls, actions)
        await db.execute(delete(Email))

        # Delete all email threads
        await db.execute(delete(EmailThread))

        # Reset last_uid to 0 so _fetch_and_save_emails does a full initial fetch
        for account in accounts:
            account.last_uid = 0

        await db.commit()

    # Re-fetch from IMAP and classify (one account at a time)
    total_fetched = 0
    for account in accounts:
        try:
            async with async_session() as db:
                # Re-load account in this session
                result = await db.execute(select(Account).where(Account.id == account.id))
                acct = result.scalar_one()

                email_ids = await _fetch_and_save_emails(db, acct)
                total_fetched += len(email_ids)

                if email_ids:
                    task = asyncio.create_task(_classify_emails_background(email_ids, acct.id))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
        except Exception:
            logger.exception("Failed to re-fetch emails for account %s", account.email)

    # Broadcast classification_started so frontend knows immediately
    if total_fetched > 0:
        from app.services.ws_manager import ws_manager

        await ws_manager.broadcast("classification_started", {"total": total_fetched})

    return {"status": "ok", "total_fetched": total_fetched}


async def cancel_all_analysis() -> dict:
    """Cancel all running background classification tasks.

    Uses cooperative cancellation (``_cancel_requested`` flag) so tasks stop
    cleanly between batches, then also calls ``task.cancel()`` as a safety net
    and awaits completion.
    """
    global _cancel_requested
    _cancel_requested = True

    cancelled = 0
    tasks_to_await = []
    for task in list(_background_tasks):
        if not task.done():
            task.cancel()
            tasks_to_await.append(task)
            cancelled += 1

    # Wait for tasks to actually finish (with a timeout)
    if tasks_to_await:
        await asyncio.gather(*tasks_to_await, return_exceptions=True)

    _background_tasks.clear()
    _cancel_requested = False

    # Count remaining unclassified emails
    remaining = 0
    try:
        async with async_session() as db:
            result = await db.execute(
                select(func.count())
                .select_from(Email)
                .where(Email.processing_status.in_(["pending", "classifying"]))
            )
            remaining = result.scalar() or 0
    except Exception:
        logger.exception("Failed to count remaining emails after cancel")

    # Broadcast cancellation event
    from app.services.ws_manager import ws_manager

    await ws_manager.broadcast(
        "classification_cancelled",
        {
            "cancelled": cancelled,
            "remaining": remaining,
        },
    )

    logger.info(
        "Cancelled %d background classification tasks, %d emails remaining", cancelled, remaining
    )
    return {"status": "ok", "cancelled": cancelled, "remaining": remaining}


async def resume_classification() -> dict:
    """Resume classification for emails stuck in pending/classifying status.

    Resets ``classifying`` emails back to ``pending``, then kicks off
    background classification for each account's unclassified emails.
    """
    total_queued = 0

    async with async_session() as db:
        # Reset classifying → pending (stale from a previous cancel)
        await db.execute(
            update(Email)
            .where(Email.processing_status == "classifying")
            .values(processing_status="pending")
        )
        await db.commit()

        # Get pending emails grouped by account
        result = await db.execute(
            select(Email.account_id, func.array_agg(Email.id))
            .where(Email.processing_status == "pending")
            .group_by(Email.account_id)
        )
        rows = result.all()

    for account_id, email_ids in rows:
        if email_ids:
            task = asyncio.create_task(_classify_emails_background(email_ids, account_id))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            total_queued += len(email_ids)

    logger.info("Resumed classification for %d emails", total_queued)
    return {"status": "ok", "total_queued": total_queued}


async def get_classification_status() -> dict:
    """Return current classification state: active flag + pending count."""
    active = any(not t.done() for t in _background_tasks)
    pending_count = 0
    try:
        async with async_session() as db:
            result = await db.execute(
                select(func.count())
                .select_from(Email)
                .where(Email.processing_status.in_(["pending", "classifying"]))
            )
            pending_count = result.scalar() or 0
    except Exception:
        logger.exception("Failed to count pending emails for status")
    return {"active": active, "pending_count": pending_count}


async def poll_account_by_id(account_id) -> dict:
    """Poll a specific account (triggered manually from API).

    Fetches and saves emails immediately (committed to DB), then kicks off
    background classification so the HTTP response returns quickly.
    """
    async with async_session() as db:
        result = await db.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()

        if not account:
            return {"error": "Account not found"}

        if not account.is_active:
            return {"error": "Account is not active"}

        try:
            # Phase 1: fetch + save emails (fast — committed immediately)
            email_ids = await _fetch_and_save_emails(db, account)

            # Phase 2: classify in background (don't block the HTTP response)
            if email_ids:
                task = asyncio.create_task(_classify_emails_background(email_ids, account.id))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

            return {
                "status": "ok",
                "account": account.email,
                "new_emails": len(email_ids),
            }
        except Exception as e:
            await db.rollback()
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Job: IMAP health check
# ---------------------------------------------------------------------------


async def check_imap_health() -> None:
    """Verify IMAP connectivity for all active accounts."""
    async with async_session() as db:
        result = await db.execute(
            select(Account).where(Account.is_active == True)  # noqa: E712
        )
        accounts = result.scalars().all()

        for account in accounts:
            try:
                password = decrypt(account.encrypted_password)
                test_result = await asyncio.to_thread(
                    imap_service.test_connection,
                    host=account.imap_host,
                    port=account.imap_port,
                    username=account.username,
                    password=password,
                    email_address=account.email,
                )

                if not test_result.success:
                    logger.warning(
                        "IMAP health check failed for %s: %s",
                        account.email,
                        test_result.error,
                    )
                    account.last_poll_error = f"Health check: {test_result.error}"
                else:
                    # Clear error if previously set from health check
                    if account.last_poll_error and account.last_poll_error.startswith(
                        "Health check:"
                    ):
                        account.last_poll_error = None

            except Exception as e:
                logger.exception("Health check error for %s", account.email)
                account.last_poll_error = f"Health check: {str(e)[:200]}"

        await db.commit()


# ---------------------------------------------------------------------------
# Job: Cleanup old data
# ---------------------------------------------------------------------------


async def cleanup_old_data() -> None:
    """Remove old activity logs and archived emails based on retention settings."""
    async with async_session() as db:
        settings = await get_settings(db)

        now = datetime.now(UTC)

        # 1. Delete old activity logs (retention_days, default 90)
        log_cutoff = now - timedelta(days=settings.retention_days)
        log_result = await db.execute(
            delete(ActivityLog).where(ActivityLog.created_at < log_cutoff)
        )
        deleted_logs = log_result.rowcount

        # 2. Archive (soft-delete) old processed emails (email_retention_days, default 365)
        email_cutoff = now - timedelta(days=settings.email_retention_days)
        email_result = await db.execute(
            select(func.count())
            .select_from(Email)
            .where(
                Email.date < email_cutoff,
                Email.is_archived == False,  # noqa: E712
            )
        )
        archivable_count = email_result.scalar() or 0

        if archivable_count > 0:
            from sqlalchemy import update

            await db.execute(
                update(Email)
                .where(Email.date < email_cutoff, Email.is_archived == False)  # noqa: E712
                .values(is_archived=True)
            )

        await db.commit()

        logger.info(
            "Cleanup complete: %d activity logs deleted, %d emails archived",
            deleted_logs,
            archivable_count,
        )


# ---------------------------------------------------------------------------
# Job: Adjust confidence threshold
# ---------------------------------------------------------------------------


async def adjust_confidence_threshold() -> dict:
    """Evaluate correction rate and adjust confidence threshold if needed."""
    from app.services.threshold_service import evaluate_and_adjust_threshold

    async with async_session() as db:
        result = await evaluate_and_adjust_threshold(db)
        await db.commit()

    logger.info("Threshold adjustment: %s", result)
    return result
