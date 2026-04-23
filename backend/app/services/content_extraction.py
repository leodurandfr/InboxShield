"""Email content extraction: HTML to Markdown, quote stripping, truncation.

Pure synchronous functions -- no I/O, no database, no LLM.
Safe to call from asyncio.to_thread().

Pipeline:
  html -> html2text -> Markdown (with inline [text](url) links)
  Markdown/text -> mail-parser-reply (strip quoted reply history)
  -> signature truncation
  -> whitespace collapse
  -> length truncation
"""

import logging
import re
import threading
from dataclasses import dataclass

import html2text
from mailparser_reply import EmailReplyParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# html2text converter -- thread-local instances (html2text.HTML2Text is
# stateful during handle(), so a shared singleton is NOT safe when called
# from multiple threads via asyncio.to_thread()).
# ---------------------------------------------------------------------------

_thread_local = threading.local()


def _get_h2t() -> html2text.HTML2Text:
    """Return a thread-local HTML2Text converter (created once per thread)."""
    if not hasattr(_thread_local, "h2t"):
        h = html2text.HTML2Text()
        h.ignore_links = False  # Preserve [text](url) inline links
        h.ignore_images = True  # Drop <img> tags (noise for LLM)
        h.ignore_tables = False  # Keep table content
        h.body_width = 0  # No line wrapping (cleaner for LLM)
        h.unicode_snob = True  # Use Unicode instead of ASCII equivalents
        h.skip_internal_links = True  # Skip anchor-only links (#section)
        h.protect_links = False  # Don't add extra markup around links
        h.ignore_mailto_links = True  # Skip mailto: links (noise)
        _thread_local.h2t = h
    return _thread_local.h2t


# ---------------------------------------------------------------------------
# mail-parser-reply instance -- supports French and English quoting patterns.
# EmailReplyParser.read() creates a new Email object per call, so the parser
# instance itself is safe to share across threads.
# ---------------------------------------------------------------------------

_reply_parser = EmailReplyParser(languages=["en", "fr"])


# ---------------------------------------------------------------------------
# Signature patterns (moved from imap_service.py)
# ---------------------------------------------------------------------------

_SIGNATURE_PATTERNS = [
    r"^--\s*$",  # Standard -- separator
    r"^_{3,}",  # ___ underscores
    r"^Envoyé depuis",  # French mobile signature
    r"^Sent from",  # English mobile signature
    r"^Get Outlook for",  # Outlook mobile
]
_SIGNATURE_RE = re.compile("|".join(_SIGNATURE_PATTERNS), re.MULTILINE | re.IGNORECASE)


# ---------------------------------------------------------------------------
# Configuration and result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ExtractionConfig:
    """Configuration for email content extraction."""

    body_max_length: int = 3000
    # HTML excerpt kept for URL analysis -- needs to be large enough
    # to capture all links in typical marketing emails.
    html_excerpt_max_length: int = 15000


@dataclass
class ExtractionResult:
    """Output of extract_email_content()."""

    body_excerpt: str  # Clean Markdown text, truncated
    body_html_excerpt: str  # Raw HTML, truncated (for URL extraction)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_email_content(
    html: str | None,
    text: str | None,
    config: ExtractionConfig | None = None,
) -> ExtractionResult:
    """Extract and clean email content from HTML and/or plain text.

    Args:
        html: Raw HTML body of the email (preferred source).
        text: Plain text body (fallback when html is absent).
        config: Extraction parameters. Uses defaults if None.

    Returns:
        ExtractionResult with body_excerpt (Markdown) and body_html_excerpt (raw HTML).
    """
    if config is None:
        config = ExtractionConfig()

    body_excerpt = _extract_body(html, text, config.body_max_length)
    body_html_excerpt = _extract_html_excerpt(html, config.html_excerpt_max_length)

    return ExtractionResult(
        body_excerpt=body_excerpt,
        body_html_excerpt=body_html_excerpt,
    )


def make_extraction_config(body_max_length: int) -> ExtractionConfig:
    """Build an ExtractionConfig from a Settings value.

    Clamps body_max_length to a minimum of 500 characters.
    """
    return ExtractionConfig(body_max_length=max(500, body_max_length))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_body(
    html: str | None,
    text: str | None,
    max_length: int,
) -> str:
    """Convert HTML to Markdown (or use plain text), strip quotes, truncate."""
    if not html and not text:
        return ""

    # Step 1: Convert HTML -> Markdown, or use plain text directly
    if html:
        try:
            content = _get_h2t().handle(html)
        except Exception:
            logger.warning("html2text failed, falling back to plain text")
            content = text or ""
    else:
        content = text or ""

    if not content.strip():
        return ""

    # Step 2: Strip quoted reply history using mail-parser-reply
    # This library understands quoting patterns from Gmail, Outlook,
    # Thunderbird, Apple Mail, etc.
    content = _strip_quoted_reply(content)

    # Step 3: Truncate at signature markers
    content = _truncate_at_signature(content)

    # Step 4: Collapse excessive whitespace while preserving Markdown structure
    content = _collapse_whitespace(content)

    # Step 5: Length truncation
    if len(content) > max_length:
        content = content[:max_length] + "..."

    return content


def _strip_quoted_reply(text: str) -> str:
    """Remove quoted email history using mail-parser-reply.

    mail-parser-reply detects quoting patterns across email clients
    and returns only the latest reply portion.
    """
    try:
        parsed = _reply_parser.read(text)
        reply = parsed.latest_reply
        if not reply:
            return text
        reply = reply.strip()
        # If stripping left us with almost nothing, return original
        # (guards against over-aggressive stripping on simple emails)
        if len(reply) < 30 and len(text.strip()) > 100:
            return text
        return reply
    except Exception:
        logger.debug("mail-parser-reply failed, using raw content")
        return text


def _truncate_at_signature(text: str) -> str:
    """Truncate content at the first signature marker."""
    match = _SIGNATURE_RE.search(text)
    if match:
        return text[: match.start()]
    return text


def _collapse_whitespace(text: str) -> str:
    """Collapse runs of 3+ blank lines to a single blank line.

    Preserves single blank lines (Markdown paragraph separators)
    but removes excessive blank lines common in HTML-converted text.
    """
    # Collapse 3+ consecutive newlines to 2 (one paragraph separator)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _extract_html_excerpt(html: str | None, max_length: int) -> str:
    """Keep a truncated raw HTML excerpt for URL extraction."""
    if not html:
        return ""
    if len(html) > max_length:
        return html[:max_length]
    return html
