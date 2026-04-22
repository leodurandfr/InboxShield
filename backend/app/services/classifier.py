"""Classifier service: full classification pipeline (sender → rules → LLM).

Pipeline:
1. Blocked sender? → skip
2. Sender profile (count >= 5, >80%) → direct classification
3. Structured rules match → rule-based classification
3b. Pre-LLM analysis: URL analysis + brand impersonation check (runs on ALL emails)
4. LLM call → AI classification
5. Smart fallback (brand check + URL analysis → phishing detection even without LLM)
6. Execute actions (move, flag, etc.)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import BaseLLMProvider, ClassificationResult
from app.models.account import Account, AccountSettings
from app.models.classification import Classification, Correction
from app.models.email import Email, EmailUrl
from app.models.rule import Rule
from app.models.settings import Settings
from app.services import activity_service, sender_service
from app.services.action_service import execute_actions
from app.services.brand_detection import BrandCheckResult, check_brand_impersonation
from app.services.llm_service import classify_email, create_provider
from app.services.rule_engine import evaluate_rules, get_default_actions
from app.services.url_analysis import UrlAnalysisResult, analyze_email_urls

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent LLM calls (don't overload Ollama or hit API limits)
_classify_semaphore = asyncio.Semaphore(5)


# ---------------------------------------------------------------------------
# Few-shot examples from corrections
# ---------------------------------------------------------------------------


async def build_few_shot_examples(
    db: AsyncSession,
    account_id: uuid.UUID,
    max_examples: int = 10,
) -> str:
    """Build few-shot examples from recent user corrections.

    These are injected into the LLM prompt so it learns from user preferences.
    """
    stmt = (
        select(Correction, Email)
        .join(Email, Correction.email_id == Email.id)
        .where(Email.account_id == account_id)
        .order_by(Correction.created_at.desc())
        .limit(max_examples)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return ""

    examples = []
    for correction, email in rows:
        examples.append(
            f'- Email de "{email.from_address}", sujet "{email.subject}" '
            f"→ {correction.corrected_category} "
            f"(initialement classé {correction.original_category})"
        )

    return "\n".join(examples)


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------


async def get_settings(db: AsyncSession) -> Settings:
    """Get global settings (singleton row)."""
    result = await db.execute(select(Settings).where(Settings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        # Create default settings on first access
        settings = Settings(id=1)
        db.add(settings)
        await db.flush()
    return settings


async def get_account_settings(db: AsyncSession, account_id: uuid.UUID) -> AccountSettings | None:
    """Get account-specific settings."""
    result = await db.execute(
        select(AccountSettings).where(AccountSettings.account_id == account_id)
    )
    return result.scalar_one_or_none()


async def get_llm_provider(db: AsyncSession) -> BaseLLMProvider:
    """Create an LLM provider from current settings."""
    settings = await get_settings(db)

    # Decrypt API key if present
    api_key = None
    if settings.llm_api_key_encrypted:
        from app.services.encryption import decrypt

        api_key = decrypt(settings.llm_api_key_encrypted)

    return create_provider(
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=api_key,
        temperature=settings.llm_temperature,
    )


# ---------------------------------------------------------------------------
# Single email classification
# ---------------------------------------------------------------------------


async def classify_single_email(
    db: AsyncSession,
    email: Email,
    account: Account,
    settings: Settings,
    llm: BaseLLMProvider | None = None,
) -> Classification | None:
    """Run the full classification pipeline on a single email.

    Returns the Classification object, or None if skipped/failed.
    """
    account_id = account.id
    from_address = email.from_address

    # -----------------------------------------------------------------------
    # Step 0: Already classified? Skip.
    # Accept "classifying" for stale retries (email stuck in classifying > 10 min).
    # -----------------------------------------------------------------------
    if email.processing_status not in ("pending", "failed", "classifying"):
        return None

    # Step 0b: Check for orphaned classification (email stuck in "pending"
    # but a Classification row already exists — caused by a previous
    # concurrent session bug).  Just fix the status and return.
    existing_classification = (
        await db.execute(
            select(Classification).where(Classification.email_id == email.id)
        )
    ).scalar_one_or_none()

    if existing_classification is not None:
        logger.info(
            "Email %s has orphaned classification (%s) — fixing status to 'classified'",
            email.id, existing_classification.category,
        )
        email.processing_status = "classified"
        from app.services.ws_manager import ws_manager
        await ws_manager.broadcast("email_classified", {
            "email_id": str(email.id),
            "category": existing_classification.category,
            "confidence": existing_classification.confidence,
            "status": existing_classification.status,
            "classified_by": existing_classification.classified_by,
        })
        return existing_classification

    # Step 0c: Claim this email for processing by setting "classifying" status.
    # This prevents concurrent tasks from double-processing the same email.
    email.processing_status = "classifying"
    await db.flush()

    # Broadcast real-time "classifying" event with metadata so the frontend
    # can display the email even if it wasn't in the visible pending list.
    from app.services.ws_manager import ws_manager
    await ws_manager.broadcast("email_classifying", {
        "email_id": str(email.id),
        "from_name": email.from_name,
        "from_address": email.from_address,
        "subject": email.subject,
        "date": str(email.date) if email.date else None,
    })

    # -----------------------------------------------------------------------
    # Step 1: Blocked sender → skip
    # -----------------------------------------------------------------------
    if await sender_service.is_sender_blocked(db, account_id, from_address):
        email.processing_status = "skipped"
        logger.info("Email %s skipped (sender blocked: %s)", email.id, from_address)
        await activity_service.log_activity(
            db,
            event_type="email_skipped",
            title=f"Email de {from_address} ignoré (expéditeur bloqué)",
            account_id=account_id,
            email_id=email.id,
        )
        return None

    # -----------------------------------------------------------------------
    # Step 2: Direct classification via sender profile
    # -----------------------------------------------------------------------
    direct_category = await sender_service.try_direct_classification(
        db, account_id, from_address
    )

    classification: Classification | None = None

    if direct_category:
        classification = Classification(
            email_id=email.id,
            category=direct_category,
            confidence=0.95,
            explanation=f"Classification directe basée sur l'historique de {from_address}",
            status="auto",
            classified_by="sender_profile",
        )
        logger.info(
            "Email %s classified directly: %s (sender_profile)",
            email.id, direct_category,
        )

    # -----------------------------------------------------------------------
    # Step 3: Structured rules evaluation
    # -----------------------------------------------------------------------
    matched_rule_ref: Rule | None = None
    if classification is None:
        matched_rule, rule_actions = await evaluate_rules(
            db, email, None, account_id, llm=llm
        )

        if matched_rule and matched_rule.category:
            matched_rule_ref = matched_rule
            classification = Classification(
                email_id=email.id,
                category=matched_rule.category,
                confidence=0.9,
                explanation=f"Classifié par la règle « {matched_rule.name} »",
                status="auto",
                classified_by="rule",
                rule_id=matched_rule.id,
            )
            logger.info(
                "Email %s classified by rule '%s': %s",
                email.id, matched_rule.name, matched_rule.category,
            )

    # -----------------------------------------------------------------------
    # Step 3b: Pre-LLM analysis (runs on ALL unclassified emails)
    # URL analysis + brand impersonation check — provides structural signals
    # that are used by the LLM prompt AND as fallback when LLM fails.
    # -----------------------------------------------------------------------
    url_analysis_result = UrlAnalysisResult()
    brand_check = BrandCheckResult()

    if classification is None:
        # Extract sender domain for URL mismatch detection
        sender_domain = None
        if email.from_address and "@" in email.from_address:
            sender_domain = email.from_address.rsplit("@", 1)[1]

        # Analyze URLs from HTML body for phishing/spam detection
        url_analysis_result = analyze_email_urls(
            email.body_html_excerpt,
            sender_domain=sender_domain,
        )

        # Check for brand impersonation (display name vs sender domain)
        brand_check = check_brand_impersonation(
            from_name=email.from_name,
            from_address=email.from_address,
        )

        # Save extracted URLs to database (regardless of LLM outcome)
        await _save_email_urls(db, email.id, url_analysis_result)

        if brand_check.is_impersonation:
            logger.warning(
                "Email %s: brand impersonation detected — '%s' claims '%s' but domain is '%s'",
                email.id, email.from_name, brand_check.claimed_brand, brand_check.actual_domain,
            )
        if url_analysis_result.has_suspicious:
            logger.warning(
                "Email %s: %d suspicious URL(s) detected",
                email.id, len(url_analysis_result.suspicious_urls),
            )

    # -----------------------------------------------------------------------
    # Step 4: LLM classification
    # -----------------------------------------------------------------------
    if classification is None and llm is not None:
        try:
            async with _classify_semaphore:
                # Build few-shot examples
                few_shot = await build_few_shot_examples(
                    db, account_id, max_examples=settings.max_few_shot_examples
                )

                url_analysis_text = url_analysis_result.to_prompt_text()
                sender_analysis_text = brand_check.to_prompt_text()

                # When the sender is NOT impersonating a brand, inject a
                # positive signal so the LLM knows URLs alone don't justify
                # a phishing classification.
                if not brand_check.is_impersonation and url_analysis_result.has_suspicious:
                    sender_analysis_text = (
                        "✓ EXPÉDITEUR VÉRIFIÉ : aucune usurpation d'identité détectée. "
                        "Le domaine de l'expéditeur correspond à l'entité annoncée. "
                        "Des URLs inhabituelles dans le corps ne suffisent PAS à "
                        "classifier en phishing si l'expéditeur est légitime."
                    )

                llm_result = await classify_email(
                    llm,
                    from_name=email.from_name or "",
                    from_address=email.from_address,
                    to_addresses=",".join(email.to_addresses or []),
                    subject=email.subject or "",
                    date=str(email.date),
                    attachments=",".join(email.attachment_names or []) if email.attachment_names else "",
                    body_excerpt=email.body_excerpt or "",
                    few_shot_examples=few_shot,
                    url_analysis=url_analysis_text,
                    sender_analysis=sender_analysis_text,
                    reply_to=getattr(email, "reply_to", None) or "",
                )

            # Determine status based on confidence and auto_mode
            if llm_result.confidence == 0.0:
                # Parse failure — try structural phishing detection before giving up
                logger.warning(
                    "LLM parse failure for email %s — attempting structural detection",
                    email.id,
                )
                structural = _try_structural_phishing_detection(
                    email, url_analysis_result, brand_check
                )
                if structural is not None:
                    classification = structural
                    logger.info(
                        "Email %s rescued from LLM failure by structural detection: phishing",
                        email.id,
                    )
                else:
                    email.processing_status = "failed"
                    email.processing_error = "Failed to parse LLM response"
                    await activity_service.log_llm_error(
                        db, account_id, f"Échec parsing pour {email.from_address}"
                    )
                    return None

            if classification is None:
                # -----------------------------------------------------------
                # Post-LLM guard: if LLM says "phishing" but the sender is
                # NOT impersonating a known brand, override the phishing
                # verdict. A legitimate sender + suspicious URLs ≠ phishing.
                # -----------------------------------------------------------
                if llm_result.is_phishing and not brand_check.is_impersonation:
                    logger.info(
                        "Email %s: LLM classified as phishing but sender is "
                        "legitimate (no brand impersonation). Overriding.",
                        email.id,
                    )
                    # Use the LLM's category if it's not "phishing", otherwise
                    # fall back to "notification".
                    safe_category = (
                        llm_result.category
                        if llm_result.category != "phishing"
                        else "notification"
                    )
                    classification = Classification(
                        email_id=email.id,
                        category=safe_category,
                        confidence=max(0.3, llm_result.confidence * 0.5),
                        explanation=(
                            f"{llm_result.explanation} "
                            "[Corrigé : expéditeur légitime, URLs suspectes insuffisantes pour phishing]"
                        ),
                        is_spam=llm_result.is_spam,
                        is_phishing=False,
                        phishing_reasons=None,
                        status="review",
                        classified_by="llm",
                        llm_provider=llm_result.provider,
                        llm_model=llm_result.model,
                        tokens_used=llm_result.tokens_used,
                        processing_time_ms=llm_result.processing_time_ms,
                    )
                else:
                    status = _determine_status(
                        llm_result, settings.confidence_threshold, settings.auto_mode
                    )

                    classification = Classification(
                        email_id=email.id,
                        category=llm_result.category,
                        confidence=llm_result.confidence,
                        explanation=llm_result.explanation,
                        is_spam=llm_result.is_spam,
                        is_phishing=llm_result.is_phishing,
                        phishing_reasons=llm_result.phishing_reasons or None,
                        status=status,
                        classified_by="llm",
                        llm_provider=llm_result.provider,
                        llm_model=llm_result.model,
                        tokens_used=llm_result.tokens_used,
                        processing_time_ms=llm_result.processing_time_ms,
                    )

                logger.info(
                    "Email %s classified by LLM: %s (conf=%.2f, status=%s)",
                    email.id, classification.category, classification.confidence,
                    classification.status,
                )

        except Exception as e:
            # LLM exception — try structural detection before marking as failed
            logger.exception("LLM classification failed for email %s", email.id)
            structural = _try_structural_phishing_detection(
                email, url_analysis_result, brand_check
            )
            if structural is not None:
                classification = structural
                logger.info(
                    "Email %s rescued from LLM exception by structural detection: phishing",
                    email.id,
                )
            else:
                email.processing_status = "failed"
                email.processing_error = str(e)
                await activity_service.log_llm_error(db, account_id, str(e))
                return None

    # -----------------------------------------------------------------------
    # Step 5: Smart fallback (no LLM available)
    # Uses structural signals (brand check + URL analysis) to detect phishing
    # even without a working LLM.
    # -----------------------------------------------------------------------
    if classification is None:
        structural = _try_structural_phishing_detection(
            email, url_analysis_result, brand_check
        )
        if structural is not None:
            classification = structural
            logger.info(
                "Email %s classified as phishing by structural detection (no LLM)",
                email.id,
            )
        else:
            logger.warning(
                "No classification for email %s (no LLM available?) — sending to review queue",
                email.id,
            )
            classification = Classification(
                email_id=email.id,
                category="notification",
                confidence=0.0,
                explanation="Classification automatique impossible (LLM indisponible). À vérifier manuellement.",
                status="review",
                classified_by="fallback",
            )

    # -----------------------------------------------------------------------
    # Step 6: Save classification + update email status
    # -----------------------------------------------------------------------
    # Guard against race condition: another process may have inserted a
    # classification between our Step 0b check and now (e.g. concurrent
    # background tasks).  Re-check right before inserting.
    race_check = (
        await db.execute(
            select(Classification).where(Classification.email_id == email.id)
        )
    ).scalar_one_or_none()
    if race_check is not None:
        logger.info(
            "Email %s: classification already exists (race) — fixing status",
            email.id,
        )
        email.processing_status = "classified"
        await db.flush()
        return race_check

    db.add(classification)
    email.processing_status = "classified"
    await db.flush()  # get classification.id

    # Broadcast real-time event
    from app.services.ws_manager import ws_manager
    await ws_manager.broadcast("email_classified", {
        "email_id": str(email.id),
        "category": classification.category,
        "confidence": classification.confidence,
        "status": classification.status,
        "classified_by": classification.classified_by,
    })

    # Update sender profile stats
    sender_profile = await sender_service.get_or_create_sender_profile(
        db, account_id, from_address, display_name=email.from_name
    )
    await sender_service.update_sender_stats(db, sender_profile, classification.category)

    # -----------------------------------------------------------------------
    # Step 7: Log activities
    # -----------------------------------------------------------------------
    await activity_service.log_email_classified(
        db,
        account_id=account_id,
        email_id=email.id,
        from_address=from_address,
        category=classification.category,
        classified_by=classification.classified_by,
    )

    if classification.is_phishing:
        await activity_service.log_phishing_detected(
            db,
            account_id=account_id,
            email_id=email.id,
            subject=email.subject or "",
            from_address=from_address,
        )

    if classification.is_spam:
        await activity_service.log_spam_detected(
            db,
            account_id=account_id,
            email_id=email.id,
            from_address=from_address,
        )

    # -----------------------------------------------------------------------
    # Step 8: Execute actions if auto-classified
    # -----------------------------------------------------------------------
    if classification.status == "auto":
        await _execute_post_classification_actions(
            db, email, account, classification, settings,
            matched_rule=matched_rule_ref,
        )

    return classification


# ---------------------------------------------------------------------------
# Status determination
# ---------------------------------------------------------------------------


def _determine_status(
    result: ClassificationResult,
    confidence_threshold: float,
    auto_mode: bool,
) -> str:
    """Determine classification status (auto/review) from result + settings."""
    if not auto_mode:
        # Manual mode: everything goes to review
        return "review"

    # Phishing always auto (to quarantine immediately)
    if result.is_phishing:
        return "auto"

    # Below confidence threshold → review
    if result.confidence < confidence_threshold:
        return "review"

    return "auto"


# ---------------------------------------------------------------------------
# Structural phishing detection (no LLM needed)
# ---------------------------------------------------------------------------


def _try_structural_phishing_detection(
    email: Email,
    url_analysis: UrlAnalysisResult,
    brand_check: BrandCheckResult,
) -> Classification | None:
    """Try to detect phishing using structural signals alone.

    Used as fallback when the LLM is unavailable or fails to parse.
    Returns a Classification if phishing is detected, or None.
    """
    reasons: list[str] = []

    if brand_check.is_impersonation:
        reasons.append(
            f"Usurpation de marque : nom « {brand_check.claimed_brand} » "
            f"mais domaine « {brand_check.actual_domain} »"
        )

    if url_analysis.has_suspicious:
        for s in url_analysis.suspicious_urls:
            for reason in s.get("reasons", []):
                reasons.append(reason)

    if not reasons:
        return None

    # For URL-only signals (no brand impersonation), require multiple strong
    # signals to avoid false positives from legitimate emails.
    # Legitimate newsletters/notifications often have URLs flagged by weak
    # heuristics (sender domain mismatch, redirect scripts, etc.).
    if not brand_check.is_impersonation:
        # Count distinct suspicious URLs (not reasons — one URL can have multiple reasons)
        n_suspicious = len(url_analysis.suspicious_urls) if url_analysis.has_suspicious else 0
        if n_suspicious < 3:
            logger.debug(
                "Structural detection skipped: only %d suspicious URL(s) and no brand impersonation",
                n_suspicious,
            )
            return None

    # Confidence: higher when both signals agree
    if brand_check.is_impersonation and url_analysis.has_suspicious:
        confidence = 0.95
    elif brand_check.is_impersonation:
        confidence = 0.85
    else:
        # URL-only suspicious (≥3 URLs): moderate confidence
        confidence = 0.75

    explanation_parts = []
    if brand_check.is_impersonation:
        explanation_parts.append(
            f"usurpation de « {brand_check.claimed_brand} » (domaine : {brand_check.actual_domain})"
        )
    if url_analysis.has_suspicious:
        explanation_parts.append(f"{len(url_analysis.suspicious_urls)} URL(s) suspecte(s)")

    # URL-only signals without brand impersonation → send to review
    # instead of auto-quarantine (too risky for false positives)
    status = "auto" if brand_check.is_impersonation else "review"

    return Classification(
        email_id=email.id,
        category="phishing",
        confidence=confidence,
        explanation=f"Phishing détecté par analyse structurelle : {', '.join(explanation_parts)}.",
        is_phishing=True,
        phishing_reasons=reasons,
        status=status,
        classified_by="structural",
    )


# ---------------------------------------------------------------------------
# Post-classification actions
# ---------------------------------------------------------------------------


async def _execute_post_classification_actions(
    db: AsyncSession,
    email: Email,
    account: Account,
    classification: Classification,
    settings: Settings,
    matched_rule: Rule | None = None,
) -> None:
    """Execute actions after auto-classification (move, flag, etc.)."""
    actions_to_run: list[dict] = []
    trigger = classification.classified_by
    rule_id: uuid.UUID | None = None

    # 1. If classified by rule, use the rule's own actions
    if matched_rule and matched_rule.actions:
        actions_to_run = matched_rule.actions
        rule_id = matched_rule.id
        trigger = "rule"

    # 2. Phishing auto-quarantine
    elif classification.is_phishing and settings.phishing_auto_quarantine:
        actions_to_run.append({"type": "move", "folder": "InboxShield/Quarantine"})
        trigger = "phishing_auto"

    # 3. Spam handling
    elif classification.is_spam:
        actions_to_run.append({"type": "move", "folder": "Junk"})
        trigger = "spam_auto"

    # 4. Default category actions from account_settings
    else:
        acct_settings = await get_account_settings(db, account.id)
        if acct_settings and acct_settings.default_category_action:
            actions_to_run = get_default_actions(
                classification.category, acct_settings.default_category_action
            )

    if not actions_to_run:
        return

    # Execute the actions
    results = await execute_actions(
        db,
        email=email,
        account_host=account.imap_host,
        account_port=account.imap_port,
        account_username=account.username,
        encrypted_password=account.encrypted_password,
        actions=actions_to_run,
        trigger=trigger,
        rule_id=rule_id,
    )

    # Log move actions to activity feed
    for action_result in results:
        if action_result["type"] == "move" and action_result["status"] == "success":
            folder = action_result.get("folder", "?")
            await activity_service.log_email_moved(
                db,
                account_id=account.id,
                email_id=email.id,
                from_address=email.from_address,
                folder=folder,
            )


# ---------------------------------------------------------------------------
# URL analysis persistence
# ---------------------------------------------------------------------------


async def _save_email_urls(
    db: AsyncSession,
    email_id: uuid.UUID,
    url_analysis: "UrlAnalysisResult",
) -> None:
    """Save extracted URLs to the email_urls table."""
    from app.services.url_analysis import UrlAnalysisResult  # noqa: F811

    if url_analysis.total_urls == 0:
        return

    # Build a mapping of suspicious domains/urls for quick lookup
    suspicious_map: dict[str, list[str]] = {}
    for s in url_analysis.suspicious_urls:
        key = s.get("url", "")
        suspicious_map[key] = s.get("reasons", [])

    # We don't re-save all URLs (could be dozens), just the unique domains
    # For efficiency, save up to 50 URLs max
    seen_urls: set[str] = set()
    from app.services.url_analysis import extract_urls_from_html  # noqa: F811

    # Re-use the already extracted data via the analysis result
    # We need the original ExtractedUrl objects, but we only have the analysis
    # So we just save suspicious ones + a sample of all domains
    for s in url_analysis.suspicious_urls:
        url_str = s.get("url", "")
        if url_str in seen_urls:
            continue
        seen_urls.add(url_str)
        email_url = EmailUrl(
            email_id=email_id,
            url=url_str,
            display_text=s.get("display_text", ""),
            domain=s.get("domain", ""),
            is_suspicious=True,
            suspicion_reason="; ".join(s.get("reasons", [])),
        )
        db.add(email_url)


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------


async def classify_batch(
    db: AsyncSession,
    emails: list[Email],
    account: Account,
) -> dict:
    """Classify a batch of emails concurrently (semaphore-limited).

    Returns stats: {"total": N, "classified": N, "skipped": N, "failed": N, "review": N}
    """
    settings = await get_settings(db)

    # Create LLM provider once for the batch
    llm: BaseLLMProvider | None = None
    try:
        llm = await get_llm_provider(db)
        if not await llm.is_available():
            logger.warning("LLM provider not available, will use sender_profile/rules only")
            llm = None
    except Exception as e:
        logger.warning("Could not create LLM provider: %s", e)
        llm = None

    stats = {"total": len(emails), "classified": 0, "skipped": 0, "failed": 0, "review": 0}

    # Process emails sequentially to avoid concurrent session access issues.
    # Use nested savepoints so a single email failure doesn't corrupt the
    # entire session (e.g. IntegrityError on duplicate classification).
    for email in emails:
        # Capture email id before savepoint — after rollback, accessing
        # ORM attributes triggers lazy-load → MissingGreenlet.
        email_id = email.id
        try:
            async with db.begin_nested():
                result = await classify_single_email(db, email, account, settings, llm)
                if result is None:
                    if email.processing_status == "skipped":
                        stats["skipped"] += 1
                    elif email.processing_status == "failed":
                        stats["failed"] += 1
                    else:
                        # Orphaned classification fixed (Step 0b) — count as classified
                        stats["classified"] += 1
                else:
                    stats["classified"] += 1
                    if result.status == "review":
                        stats["review"] += 1
        except Exception:
            stats["failed"] += 1
            logger.exception("Unexpected error classifying email %s", email_id)
            # Session was rolled back to the savepoint — mark email as failed
            # in a fresh savepoint so the rest of the batch can continue.
            try:
                async with db.begin_nested():
                    await db.execute(
                        Email.__table__.update()
                        .where(Email.id == email_id)
                        .values(processing_status="failed")
                    )
            except Exception:
                pass  # non-critical, will be retried later

    logger.info(
        "Batch classification complete: %d total, %d classified, %d skipped, %d failed, %d review",
        stats["total"], stats["classified"], stats["skipped"], stats["failed"], stats["review"],
    )

    return stats


# ---------------------------------------------------------------------------
# Re-classification (for manual retry of failed emails)
# ---------------------------------------------------------------------------


async def reclassify_email(
    db: AsyncSession,
    email: Email,
    account: Account,
) -> Classification | None:
    """Re-classify a failed or already-classified email.

    Deletes existing classification and runs the pipeline again.
    """
    # Remove existing classification if any (use direct query to avoid
    # MissingGreenlet from lazy-loading the relationship in async context)
    existing = (
        await db.execute(
            select(Classification).where(Classification.email_id == email.id)
        )
    ).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    # Reset status to pending
    email.processing_status = "pending"
    email.processing_error = None

    settings = await get_settings(db)
    llm = await get_llm_provider(db)

    return await classify_single_email(db, email, account, settings, llm)


# ---------------------------------------------------------------------------
# Review actions (approve / correct)
# ---------------------------------------------------------------------------


async def approve_classification(
    db: AsyncSession,
    classification: Classification,
    email: Email,
    account: Account,
) -> None:
    """Approve a review classification → execute actions."""
    classification.status = "approved"

    # Update sender profile
    sender_profile = await sender_service.get_or_create_sender_profile(
        db, account.id, email.from_address, display_name=email.from_name
    )
    await sender_service.update_sender_stats(db, sender_profile, classification.category)

    # Log
    await activity_service.log_review_approved(
        db,
        account_id=account.id,
        email_id=email.id,
        from_address=email.from_address,
        category=classification.category,
    )

    # Execute actions
    settings = await get_settings(db)
    await _execute_post_classification_actions(db, email, account, classification, settings)


async def correct_classification(
    db: AsyncSession,
    classification: Classification,
    email: Email,
    account: Account,
    corrected_category: str,
    user_note: str | None = None,
) -> Correction:
    """Correct a classification → create correction record + update sender stats."""
    original_category = classification.category
    original_confidence = classification.confidence

    # Update classification
    classification.category = corrected_category
    classification.status = "corrected"
    classification.confidence = 1.0  # User-corrected = 100% confidence

    # Create correction record (for few-shot learning)
    correction = Correction(
        email_id=email.id,
        classification_id=classification.id,
        original_category=original_category,
        corrected_category=corrected_category,
        original_confidence=original_confidence,
        user_note=user_note,
    )
    db.add(correction)

    # Update sender profile with correction (double weight)
    sender_profile = await sender_service.get_or_create_sender_profile(
        db, account.id, email.from_address, display_name=email.from_name
    )
    await sender_service.update_sender_stats(
        db, sender_profile, corrected_category, is_correction=True
    )

    # Log
    await activity_service.log_review_corrected(
        db,
        account_id=account.id,
        email_id=email.id,
        from_address=email.from_address,
        original_category=original_category,
        corrected_category=corrected_category,
    )

    # Execute actions with the corrected category
    settings = await get_settings(db)
    await _execute_post_classification_actions(db, email, account, classification, settings)

    return correction
