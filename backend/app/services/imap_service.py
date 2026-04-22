"""IMAP service: connection, folder discovery, email fetching, and IMAP operations."""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from imap_tools import AND, MailBox, MailboxLoginError, MailMessage, MailMessageFlags

from app.services.content_extraction import (
    ExtractionConfig,
    extract_email_content,
)

logger = logging.getLogger(__name__)

# Default timeout for IMAP connections (seconds)
IMAP_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Provider auto-detection map
# ---------------------------------------------------------------------------

PROVIDER_MAP: dict[str, dict] = {
    # GMX
    "gmx.com": {"host": "imap.gmx.com", "port": 993, "smtp_host": "mail.gmx.com", "smtp_port": 587},
    "gmx.fr": {"host": "imap.gmx.com", "port": 993, "smtp_host": "mail.gmx.com", "smtp_port": 587},
    "gmx.de": {"host": "imap.gmx.net", "port": 993, "smtp_host": "mail.gmx.net", "smtp_port": 587},
    "gmx.net": {"host": "imap.gmx.net", "port": 993, "smtp_host": "mail.gmx.net", "smtp_port": 587},
    # Gmail
    "gmail.com": {"host": "imap.gmail.com", "port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587},
    "googlemail.com": {"host": "imap.gmail.com", "port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587},
    # Outlook / Microsoft
    "outlook.com": {"host": "outlook.office365.com", "port": 993, "smtp_host": "smtp.office365.com", "smtp_port": 587},
    "hotmail.com": {"host": "outlook.office365.com", "port": 993, "smtp_host": "smtp.office365.com", "smtp_port": 587},
    "live.com": {"host": "outlook.office365.com", "port": 993, "smtp_host": "smtp.office365.com", "smtp_port": 587},
    "msn.com": {"host": "outlook.office365.com", "port": 993, "smtp_host": "smtp.office365.com", "smtp_port": 587},
    # Yahoo
    "yahoo.com": {"host": "imap.mail.yahoo.com", "port": 993, "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 587},
    "yahoo.fr": {"host": "imap.mail.yahoo.com", "port": 993, "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 587},
    # Fastmail
    "fastmail.com": {"host": "imap.fastmail.com", "port": 993, "smtp_host": "smtp.fastmail.com", "smtp_port": 587},
    # ProtonMail (via Bridge)
    "protonmail.com": {"host": "127.0.0.1", "port": 1143, "smtp_host": "127.0.0.1", "smtp_port": 1025, "note": "ProtonMail Bridge required"},
    "proton.me": {"host": "127.0.0.1", "port": 1143, "smtp_host": "127.0.0.1", "smtp_port": 1025, "note": "ProtonMail Bridge required"},
    # iCloud
    "icloud.com": {"host": "imap.mail.me.com", "port": 993, "smtp_host": "smtp.mail.me.com", "smtp_port": 587},
    "me.com": {"host": "imap.mail.me.com", "port": 993, "smtp_host": "smtp.mail.me.com", "smtp_port": 587},
}

# Known folder names by role for common providers
_FOLDER_ALIASES: dict[str, list[str]] = {
    "inbox": ["INBOX"],
    "sent": ["Sent", "Sent Items", "Sent Mail", "[Gmail]/Sent Mail", "INBOX.Sent"],
    "drafts": ["Drafts", "[Gmail]/Drafts", "INBOX.Drafts"],
    "spam": ["Spam", "Junk", "Junk Email", "Junk Mail", "[Gmail]/Spam", "INBOX.Spam", "INBOX.Junk"],
    "trash": ["Trash", "Deleted Items", "Deleted Messages", "[Gmail]/Trash", "INBOX.Trash"],
}


# ---------------------------------------------------------------------------
# Data classes for return values
# ---------------------------------------------------------------------------


@dataclass
class ProviderInfo:
    provider: str | None
    host: str
    port: int
    smtp_host: str | None = None
    smtp_port: int | None = None
    note: str | None = None


@dataclass
class FolderMapping:
    folders: list[str]
    suggested_mapping: dict[str, str]


@dataclass
class FetchedEmail:
    """Raw email data extracted from IMAP, ready to be saved to DB."""
    uid: int
    message_id: str | None
    in_reply_to: str | None
    references: str | None
    from_address: str
    from_name: str | None
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str | None
    body_excerpt: str
    body_html_excerpt: str
    has_attachments: bool
    attachment_names: list[str]
    date: datetime
    folder: str
    is_read: bool
    is_flagged: bool
    size_bytes: int
    # Raw headers for newsletter detection
    list_unsubscribe: str | None = None
    list_unsubscribe_post: str | None = None
    # Reply-To header (phishing detection — often differs from From)
    reply_to: str | None = None


@dataclass
class ConnectionTestResult:
    success: bool
    provider: str | None = None
    folders: list[str] = field(default_factory=list)
    suggested_mapping: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def detect_provider(email: str) -> ProviderInfo | None:
    """Detect IMAP provider from email domain. Returns None if unknown."""
    domain = email.rsplit("@", 1)[-1].lower()
    info = PROVIDER_MAP.get(domain)
    if info:
        return ProviderInfo(
            provider=domain.split(".")[0],
            host=info["host"],
            port=info["port"],
            smtp_host=info.get("smtp_host"),
            smtp_port=info.get("smtp_port"),
            note=info.get("note"),
        )
    return None


# ---------------------------------------------------------------------------
# Folder discovery & mapping
# ---------------------------------------------------------------------------


def _suggest_folder_mapping(folder_list: list[str]) -> dict[str, str]:
    """Map logical folder roles to actual IMAP folder names."""
    mapping: dict[str, str] = {}
    lower_map = {f.lower(): f for f in folder_list}

    for role, aliases in _FOLDER_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower_map:
                mapping[role] = lower_map[alias.lower()]
                break

    return mapping


# ---------------------------------------------------------------------------
# Default extraction config (used when no ExtractionConfig is provided)
# ---------------------------------------------------------------------------

_DEFAULT_EXTRACTION_CONFIG = ExtractionConfig()


# ---------------------------------------------------------------------------
# IMAP operations
# ---------------------------------------------------------------------------


def test_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    email_address: str | None = None,
) -> ConnectionTestResult:
    """Test IMAP connection without saving. Returns folders on success."""
    provider_info = detect_provider(email_address) if email_address else None

    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password) as mailbox:
            folders = [f.name for f in mailbox.folder.list()]
            suggested = _suggest_folder_mapping(folders)

            return ConnectionTestResult(
                success=True,
                provider=provider_info.provider if provider_info else None,
                folders=folders,
                suggested_mapping=suggested,
            )
    except MailboxLoginError:
        return ConnectionTestResult(
            success=False,
            error="Identifiants incorrects",
            error_code="AUTH_FAILED",
        )
    except TimeoutError:
        return ConnectionTestResult(
            success=False,
            error="Connexion timeout — vérifiez l'hôte et le port",
            error_code="TIMEOUT",
        )
    except Exception as e:
        return ConnectionTestResult(
            success=False,
            error=str(e),
            error_code="CONNECTION_ERROR",
        )


def discover_folders(host: str, port: int, username: str, password: str) -> FolderMapping:
    """List all IMAP folders and suggest a logical mapping."""
    with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password) as mailbox:
        folders = [f.name for f in mailbox.folder.list()]
        return FolderMapping(
            folders=folders,
            suggested_mapping=_suggest_folder_mapping(folders),
        )


def _extract_email(
    msg: MailMessage,
    folder: str,
    config: ExtractionConfig | None = None,
) -> FetchedEmail:
    """Extract structured data from an imap_tools MailMessage."""
    # Parse from
    from_addr = msg.from_ or ""
    from_name = ""
    if msg.from_values:
        from_name = msg.from_values.name or ""
        from_addr = msg.from_values.email or from_addr

    # Parse to/cc
    to_addresses = [v.email for v in (msg.to_values or []) if v.email]
    cc_addresses = [v.email for v in (msg.cc_values or []) if v.email]

    # Attachments
    attachments = list(msg.attachments)
    attachment_names = [a.filename for a in attachments if a.filename]

    # Body: use content_extraction module (html2text + mail-parser-reply)
    extraction = extract_email_content(
        html=msg.html,
        text=msg.text,
        config=config or _DEFAULT_EXTRACTION_CONFIG,
    )

    # Headers for newsletter detection
    list_unsub = msg.headers.get("list-unsubscribe", [""])[0] if msg.headers else None
    list_unsub_post = msg.headers.get("list-unsubscribe-post", [""])[0] if msg.headers else None

    # Reply-To header (phishing detection — often differs from From)
    reply_to_raw = msg.headers.get("reply-to", [""])[0] if msg.headers else None
    reply_to = None
    if reply_to_raw:
        # Extract email address from "Name <email>" format
        match = re.search(r"<([^>]+)>", reply_to_raw)
        reply_to = match.group(1) if match else reply_to_raw.strip()

    return FetchedEmail(
        uid=msg.uid if isinstance(msg.uid, int) else int(msg.uid),
        message_id=msg.headers.get("message-id", [""])[0] if msg.headers else None,
        in_reply_to=msg.headers.get("in-reply-to", [""])[0] if msg.headers else None,
        references=msg.headers.get("references", [""])[0] if msg.headers else None,
        from_address=from_addr,
        from_name=from_name,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=msg.subject,
        body_excerpt=extraction.body_excerpt,
        body_html_excerpt=extraction.body_html_excerpt,
        has_attachments=len(attachments) > 0,
        attachment_names=attachment_names,
        date=msg.date or datetime.now(),
        folder=folder,
        is_read=MailMessageFlags.SEEN in (msg.flags or ()),
        is_flagged=MailMessageFlags.FLAGGED in (msg.flags or ()),
        size_bytes=msg.size or 0,
        list_unsubscribe=list_unsub or None,
        list_unsubscribe_post=list_unsub_post or None,
        reply_to=reply_to or None,
    )


def fetch_new_emails(
    host: str,
    port: int,
    username: str,
    password: str,
    folder: str = "INBOX",
    since_uid: int = 0,
    config: ExtractionConfig | None = None,
) -> list[FetchedEmail]:
    """Fetch emails with UID > since_uid from the given folder."""
    emails: list[FetchedEmail] = []

    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password, initial_folder=folder) as mailbox:
            # Fetch by UID range: since_uid+1 to *
            uid_criteria = f"{since_uid + 1}:*" if since_uid > 0 else "1:*"
            messages = mailbox.fetch(
                AND(uid=uid_criteria),
                mark_seen=False,
                bulk=True,
            )

            for msg in messages:
                msg_uid = msg.uid if isinstance(msg.uid, int) else int(msg.uid)
                # imap_tools might return the since_uid itself, filter it
                if msg_uid <= since_uid:
                    continue
                try:
                    emails.append(_extract_email(msg, folder, config))
                except Exception:
                    logger.exception("Failed to parse email UID %s", msg.uid)

    except MailboxLoginError:
        logger.error("IMAP auth failed for %s@%s", username, host)
        raise
    except Exception:
        logger.exception("IMAP fetch error for %s@%s folder=%s", username, host, folder)
        raise

    return emails


def fetch_recent_emails(
    host: str,
    port: int,
    username: str,
    password: str,
    folder: str = "INBOX",
    limit: int = 100,
    config: ExtractionConfig | None = None,
) -> list[FetchedEmail]:
    """Fetch the N most recent emails (for onboarding initial scan)."""
    emails: list[FetchedEmail] = []

    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password, initial_folder=folder) as mailbox:
            messages = mailbox.fetch(
                AND(all=True),
                mark_seen=False,
                reverse=True,
                limit=limit,
                bulk=True,
            )

            for msg in messages:
                try:
                    emails.append(_extract_email(msg, folder, config))
                except Exception:
                    logger.exception("Failed to parse email UID %s", msg.uid)

    except Exception:
        logger.exception("IMAP fetch_recent error for %s@%s", username, host)
        raise

    # Return in chronological order (oldest first)
    emails.reverse()
    return emails


def fetch_emails_since(
    host: str,
    port: int,
    username: str,
    password: str,
    folder: str = "INBOX",
    since_date: date | datetime | None = None,
    config: ExtractionConfig | None = None,
) -> list[FetchedEmail]:
    """Fetch all emails since a given date from a folder (no limit).

    If since_date is None, fetches from the 1st of the current month.
    """
    if since_date is None:
        today = date.today()
        since = today.replace(day=1)
    elif isinstance(since_date, datetime):
        since = since_date.date()
    else:
        since = since_date

    emails: list[FetchedEmail] = []

    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password, initial_folder=folder) as mailbox:
            messages = mailbox.fetch(
                AND(date_gte=since),
                mark_seen=False,
                bulk=True,
            )

            for msg in messages:
                try:
                    emails.append(_extract_email(msg, folder, max_body))
                except Exception:
                    logger.exception("Failed to parse email UID %s in %s", msg.uid, folder)

    except Exception:
        logger.exception("IMAP fetch_since error for %s@%s folder=%s since=%s", username, host, folder, since)
        raise

    logger.info("Fetched %d emails from %s since %s", len(emails), folder, since)
    return emails


# ---------------------------------------------------------------------------
# IMAP write operations
# ---------------------------------------------------------------------------


def move_email(
    host: str, port: int, username: str, password: str,
    uid: int, from_folder: str, to_folder: str,
) -> bool:
    """Move an email to another IMAP folder."""
    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password, initial_folder=from_folder) as mailbox:
            mailbox.move(str(uid), to_folder)
            return True
    except Exception:
        logger.exception("Failed to move UID %s from %s to %s", uid, from_folder, to_folder)
        raise


def set_flag(
    host: str, port: int, username: str, password: str,
    uid: int, folder: str, flag: str, value: bool = True,
) -> bool:
    """Set or unset an IMAP flag on an email."""
    flag_map = {
        "seen": MailMessageFlags.SEEN,
        "read": MailMessageFlags.SEEN,
        "flagged": MailMessageFlags.FLAGGED,
        "important": MailMessageFlags.FLAGGED,
    }

    imap_flag = flag_map.get(flag.lower())
    if not imap_flag:
        raise ValueError(f"Unknown flag: {flag}. Supported: {list(flag_map.keys())}")

    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password, initial_folder=folder) as mailbox:
            mailbox.flag(str(uid), {imap_flag}, value)
            return True
    except Exception:
        logger.exception("Failed to set flag %s on UID %s in %s", flag, uid, folder)
        raise


def create_folder(
    host: str, port: int, username: str, password: str,
    folder_name: str,
) -> bool:
    """Create an IMAP folder (e.g., InboxShield/Quarantine)."""
    try:
        with MailBox(host, port, timeout=IMAP_TIMEOUT).login(username, password) as mailbox:
            mailbox.folder.create(folder_name)
            return True
    except Exception:
        logger.exception("Failed to create folder %s", folder_name)
        raise
