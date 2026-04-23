"""Newsletter detection, stats, and unsubscribe."""

import logging
import re
import uuid
from datetime import UTC, datetime

import aiosmtplib
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.newsletter import Newsletter
from app.services.encryption import decrypt

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0
_UNSUB_TEXT_PATTERNS = ("unsubscribe", "désabonner", "désinscri", "opt-out", "se désinscrire")


# ---------------------------------------------------------------------------
# Extraction — build unsubscribe info from an email's headers / body
# ---------------------------------------------------------------------------


def extract_unsubscribe_info(
    list_unsubscribe: str | None,
    list_unsubscribe_post: str | None = None,
    body_html: str | None = None,
) -> dict | None:
    """Extract unsubscribe link/mailto/method from IMAP headers + body.

    Returns {"link": str | None, "mailto": str | None, "method": str} or None.
    Methods: "http_post" (RFC 8058 one-click), "http_get", "mailto", "manual".
    """
    if list_unsubscribe:
        urls = re.findall(r"<(https?://[^>]+)>", list_unsubscribe)
        mailtos = re.findall(r"<mailto:([^>]+)>", list_unsubscribe)
        has_one_click = bool(
            list_unsubscribe_post and "List-Unsubscribe=One-Click" in list_unsubscribe_post
        )
        if urls or mailtos:
            if urls and has_one_click:
                method = "http_post"
            elif urls:
                method = "http_get"
            else:
                method = "mailto"
            return {
                "link": urls[0] if urls else None,
                "mailto": mailtos[0] if mailtos else None,
                "method": method,
            }

    # Fallback: scan HTML for a plausible unsubscribe anchor.
    if body_html:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        try:
            soup = BeautifulSoup(body_html, "html.parser")
        except Exception:
            return None
        for link in soup.find_all("a"):
            text = (link.get_text() or "").lower()
            href = link.get("href") or ""
            if any(kw in text for kw in _UNSUB_TEXT_PATTERNS) and href.startswith("http"):
                return {"link": href, "mailto": None, "method": "manual"}

    return None


# ---------------------------------------------------------------------------
# Aggregated stats for /newsletters/stats
# ---------------------------------------------------------------------------


async def compute_newsletter_stats(
    db: AsyncSession,
    account_id: uuid.UUID | None = None,
) -> dict:
    base = select(Newsletter)
    if account_id:
        base = base.where(Newsletter.account_id == account_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    subscribed = (
        await db.execute(
            select(func.count()).select_from(
                base.where(Newsletter.subscription_status == "subscribed").subquery()
            )
        )
    ).scalar() or 0

    unsubscribed = (
        await db.execute(
            select(func.count()).select_from(
                base.where(Newsletter.subscription_status == "unsubscribed").subquery()
            )
        )
    ).scalar() or 0

    received_sum = (
        await db.execute(select(func.coalesce(func.sum(Newsletter.total_received), 0)))
    ).scalar() or 0
    read_sum = (
        await db.execute(select(func.coalesce(func.sum(Newsletter.total_read), 0)))
    ).scalar() or 0
    read_rate = (read_sum / received_sum) if received_sum else 0.0

    never_read = (
        await db.execute(
            select(func.count()).select_from(base.where(Newsletter.total_read == 0).subquery())
        )
    ).scalar() or 0

    return {
        "total": total,
        "subscribed": subscribed,
        "unsubscribed": unsubscribed,
        "read_rate": round(read_rate, 3),
        "never_read": never_read,
    }


# ---------------------------------------------------------------------------
# Unsubscribe — HTTP POST (RFC 8058), HTTP GET, or SMTP mailto
# ---------------------------------------------------------------------------


async def unsubscribe_newsletter(
    db: AsyncSession,
    newsletter: Newsletter,
) -> dict:
    """Execute the unsubscribe flow for one newsletter.

    Returns {"status": "success" | "failed" | "manual", "message": str}.
    On success, flips subscription_status/unsubscribed_at and commits via the
    caller's session (no explicit commit here).
    """
    method = newsletter.unsubscribe_method
    link = newsletter.unsubscribe_link
    mailto = newsletter.unsubscribe_mailto

    if not method or (not link and not mailto):
        return {
            "status": "manual",
            "message": "Aucun lien de désinscription détecté — action manuelle requise.",
        }

    outcome: dict
    if method == "http_post" and link:
        outcome = await _try_http_post(link)
    elif method == "http_get" and link:
        outcome = await _try_http_get(link)
    elif method == "mailto" and mailto:
        outcome = await _try_mailto(db, newsletter, mailto)
    elif method == "manual":
        return {
            "status": "manual",
            "message": "Désinscription manuelle requise — suivez le lien.",
        }
    else:
        return {"status": "failed", "message": f"Méthode inconnue : {method}"}

    if outcome["status"] == "success":
        newsletter.subscription_status = "unsubscribed"
        newsletter.unsubscribed_at = datetime.now(UTC)
    else:
        newsletter.subscription_status = "failed"

    return outcome


async def _try_http_post(url: str) -> dict:
    """RFC 8058 one-click unsubscribe: POST with form-encoded body."""
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.post(
                url,
                data={"List-Unsubscribe": "One-Click"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        logger.warning("http_post unsubscribe failed for %s: %s", url, exc)
        return {"status": "failed", "message": f"Erreur HTTP : {exc}"}

    if resp.status_code in (200, 202, 204):
        return {
            "status": "success",
            "message": f"Désinscription confirmée (HTTP {resp.status_code})",
        }
    return {
        "status": "failed",
        "message": f"Réponse inattendue du serveur (HTTP {resp.status_code})",
    }


async def _try_http_get(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("http_get unsubscribe failed for %s: %s", url, exc)
        return {"status": "failed", "message": f"Erreur HTTP : {exc}"}

    if resp.status_code == 200:
        return {
            "status": "success",
            "message": (
                "Requête envoyée. Certains services exigent une confirmation "
                "sur la page — vérifiez si besoin."
            ),
        }
    return {
        "status": "failed",
        "message": f"Réponse inattendue du serveur (HTTP {resp.status_code})",
    }


async def _try_mailto(
    db: AsyncSession,
    newsletter: Newsletter,
    mailto: str,
) -> dict:
    """Send an empty unsubscribe email via the account's SMTP."""
    target, _, _query = mailto.partition("?")
    if not target:
        return {"status": "failed", "message": "Adresse mailto invalide"}

    account = (
        await db.execute(select(Account).where(Account.id == newsletter.account_id))
    ).scalar_one_or_none()
    if not account:
        return {"status": "failed", "message": "Compte introuvable"}

    if not account.smtp_host:
        return {
            "status": "failed",
            "message": "SMTP non configuré pour ce compte — désinscription mailto impossible.",
        }

    try:
        password = decrypt(account.encrypted_password)
    except Exception as exc:
        logger.warning("SMTP credential decrypt failed for %s: %s", account.email, exc)
        return {"status": "failed", "message": "Erreur de déchiffrement SMTP"}

    message = f"From: {account.email}\r\nTo: {target}\r\nSubject: unsubscribe\r\n\r\n"

    try:
        await aiosmtplib.send(
            message,
            sender=account.email,
            recipients=[target],
            hostname=account.smtp_host,
            port=account.smtp_port or 587,
            username=account.username,
            password=password,
            start_tls=True,
            timeout=15,
        )
    except Exception as exc:
        logger.warning("mailto unsubscribe failed via %s: %s", account.smtp_host, exc)
        return {"status": "failed", "message": f"Erreur SMTP : {exc}"}

    return {
        "status": "success",
        "message": f"Email de désinscription envoyé à {target}",
    }


# ---------------------------------------------------------------------------
# Detection + stats refresh for a specific newsletter (called from pipeline)
# ---------------------------------------------------------------------------


async def detect_or_update_newsletter(
    db: AsyncSession,
    account_id: uuid.UUID,
    sender_address: str,
    unsubscribe_info: dict | None,
    is_read: bool,
    email_date: datetime | None,
    display_name: str | None = None,
) -> Newsletter | None:
    """Upsert a newsletter row when the email carries unsubscribe info.

    Safe to call for every classified email — returns None if the email does
    not look like a newsletter (no unsubscribe info, no prior row).
    """
    existing = (
        await db.execute(
            select(Newsletter).where(
                Newsletter.account_id == account_id,
                Newsletter.sender_address == sender_address,
            )
        )
    ).scalar_one_or_none()

    if existing is None and not unsubscribe_info:
        return None

    if existing is None:
        existing = Newsletter(
            account_id=account_id,
            sender_address=sender_address,
            name=display_name,
            total_received=0,
            total_read=0,
            subscription_status="subscribed",
        )
        db.add(existing)

    if unsubscribe_info:
        existing.unsubscribe_link = unsubscribe_info.get("link") or existing.unsubscribe_link
        existing.unsubscribe_mailto = unsubscribe_info.get("mailto") or existing.unsubscribe_mailto
        existing.unsubscribe_method = unsubscribe_info.get("method") or existing.unsubscribe_method

    existing.total_received = (existing.total_received or 0) + 1
    if is_read:
        existing.total_read = (existing.total_read or 0) + 1
    if email_date and (existing.last_received_at is None or email_date > existing.last_received_at):
        existing.last_received_at = email_date

    return existing
