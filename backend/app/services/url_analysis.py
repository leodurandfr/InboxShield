"""URL analysis service for phishing and spam detection.

Extracts URLs from HTML email bodies and applies heuristic checks
to detect suspicious patterns:

Phase 1 (original):
  1. Mismatched display text vs actual href domain
  2. Homoglyphs in domain (Cyrillic chars mimicking Latin)
  3. URL shorteners
  4. IP-based URLs
  5. Deceptive subdomains (paypal.com.evil.xyz)

Phase 2 (enhanced fraud detection):
  6. Base64-encoded URLs hidden in query parameters
  7. Email address embedded in URL parameters (tracking/harvesting)
  8. Redirect/click tracker scripts (click.php, redirect, etc.)
  9. Suspicious random/gibberish domains (dfhv4y.com)
  10. Affiliate spam parameters (aff_id, offer_id, etc.)
  11. Sender domain mismatch (URL domains unrelated to sender)

See docs/03c-SPAM-PHISHING-DETECTION.md for spec.
"""

import base64
import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from tldextract import TLDExtract

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# tldextract -- uses the Public Suffix List for accurate domain extraction.
# Module-level singleton: PSL is loaded once from bundled snapshot.
# ---------------------------------------------------------------------------

_tld_extract = TLDExtract(include_psl_private_domains=False)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Well-known URL shortener domains
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "bl.ink", "lnkd.in", "db.tt", "qr.ae",
    "rebrand.ly", "short.io", "cutt.ly", "rb.gy", "t.ly", "v.gd",
    "shorturl.at", "tiny.cc",
}

# Known LEGITIMATE email tracking/redirect service domains.
# These services wrap legitimate URLs for tracking purposes, so
# a mismatch between display text and href is expected and NOT suspicious.
KNOWN_TRACKING_DOMAINS = {
    "list-manage.com", "mailchimp.com", "sendgrid.net", "mandrillapp.com",
    "mailgun.net", "sparkpostmail.com", "createsend.com",
    "cmail19.com", "cmail20.com", "campaign-archive.com", "mcsv.net",
    "hubspot.com", "hubspotlinks.com", "mktomail.com", "marketo.com",
    "pardot.com", "eloqua.com", "constantcontact.com", "sailthru.com",
    "brevo.com", "sendinblue.com",
    # Sendinblue/Brevo transactional domains (sendibt2, sendibt3, sendibt4, etc.)
    "sendibt2.com", "sendibt3.com", "sendibt4.com",
    # AWS SES tracking
    "awstrack.me", "amazonses.com",
    # Marketing / analytics / CRM platforms used by legitimate senders
    "delight-data.com",  # Delight Data (email marketing analytics)
    "pegacloud.io",  # Pega Cloud (CRM surveys, e.g., Transavia)
    "sib.asso.fr",  # Sendinblue France
    "mailjet.com",
    "mjt.lu",  # Mailjet short tracking domain (e.g., x7p5o.mjt.lu)
    "getresponse.com",
    "klaviyo.com",
    "klclick.com",  # Klaviyo click tracking (ctrk.klclick.com)
    "activecampaign.com",
    "drip.com",
    "convertkit.com",
    "customer.io",
    "intercom.io",
    "zendesk.com",
    # Additional tracking/redirect platforms
    "emarsys.net",
    "emarsys.com",
    "returnpath.net",
    "litmus.com",
    "mailgun.com",
    "postmarkapp.com",
    "mailtrap.io",
    "moosend.com",
    "omnisend.com",
    "campaignmonitor.com",
    "infomaniak.com",
    "tipimail.com",
}

# Subdomain prefixes for tracking services.
# SECURITY: prefix alone is NOT sufficient -- the parent domain must also be
# in KNOWN_TRACKING_DOMAINS. Otherwise an attacker can use "click.evil.xyz"
# to bypass all heuristics.
KNOWN_TRACKING_PREFIXES = {
    "click.", "track.", "email.", "links.", "link.", "go.", "trk.", "t.",
    "e.", "r.", "u.", "l.", "m.", "open.", "redirect.", "mailer.", "follow.",
}

# Characters that look like Latin but are from other scripts (homoglyphs)
HOMOGLYPH_MAP = {
    "\u0430": "a",  # Cyrillic а
    "\u0435": "e",  # Cyrillic е
    "\u043e": "o",  # Cyrillic о
    "\u0440": "p",  # Cyrillic р
    "\u0441": "c",  # Cyrillic с
    "\u0443": "y",  # Cyrillic у
    "\u0445": "x",  # Cyrillic х
    "\u0456": "i",  # Cyrillic і
    "\u0501": "d",  # Cyrillic ԁ
    "\u051b": "q",  # Cyrillic ԛ
    "\u0261": "g",  # Latin small script g
}

# Common TLDs for legitimate services (used for subdomain deception check)
COMMON_LEGITIMATE_DOMAINS = {
    # International tech
    "google.com", "apple.com", "microsoft.com", "amazon.com", "amazon.fr",
    "paypal.com", "facebook.com", "instagram.com", "twitter.com",
    "linkedin.com", "github.com", "netflix.com", "spotify.com",
    # French energy / utilities
    "edf.fr", "edf.com", "engie.fr", "totalenergies.fr",
    # French government / public services
    "ameli.fr", "impots.gouv.fr", "caf.fr", "pole-emploi.fr", "francetravail.fr",
    "ants.gouv.fr", "antai.gouv.fr",
    # French banks
    "labanquepostale.fr", "credit-agricole.fr", "bnpparibas.fr",
    "societegenerale.fr", "lcl.fr", "boursorama.fr", "boursobank.com",
    "creditmutuel.fr", "caisse-epargne.fr",
    # French telecom
    "orange.fr", "sfr.fr", "free.fr", "bouyguestelecom.fr",
    # French postal / delivery
    "laposte.fr", "laposte.net", "colissimo.fr", "chronopost.fr",
    # E-commerce
    "cdiscount.com", "fnac.com", "darty.com", "leboncoin.fr", "vinted.fr",
}

# Personal / webmail / free email provider "core" domain names.
# When the sender is from one of these, URL domain mismatch is expected
# (people forward emails, share links, etc.) — skip heuristic #11.
PERSONAL_WEBMAIL_DOMAINS = {
    "gmail", "googlemail", "outlook", "hotmail", "live", "msn",
    "yahoo", "ymail", "aol", "icloud", "me", "mac",
    "protonmail", "proton", "tutanota", "tuta",
    "gmx", "web",  # gmx.com/net/de/fr, web.de
    "mail",  # mail.com, mail.ru
    "laposte",  # laposte.net (French free mail)
    "free",  # free.fr
    "orange",  # orange.fr (personal email)
    "sfr",  # sfr.fr
    "wanadoo",  # wanadoo.fr
    "bbox",  # bbox.fr (Bouygues)
    "t-online",  # t-online.de
    "posteo",  # posteo.de
    "zoho",
    "yandex",
    "fastmail",
}

# Related domain groups — organizations that legitimately cross-link
# between multiple official domains they own/operate.
# Each group is a frozenset of "core" domain parts.
RELATED_DOMAIN_GROUPS: list[frozenset[str]] = [
    # French social/government — URSSAF ecosystem
    frozenset({"urssaf", "net-entreprises", "letese", "cea", "tfe", "acoss", "pajemploi"}),
    # French tax / finances
    frozenset({"impots", "dgfip", "finances", "economie", "tresor"}),
    # French health insurance
    frozenset({"ameli", "assurance-maladie", "cpam"}),
    # French employment
    frozenset({"pole-emploi", "francetravail"}),
    # French postal group (includes notification domains)
    frozenset({"laposte", "colissimo", "chronopost", "digiposte",
               "notif-colissimo-laposte"}),
    # French education / research
    frozenset({"education", "ac-paris", "ac-lyon", "ac-versailles", "cnrs", "inria"}),
    # Google ecosystem
    frozenset({"google", "youtube", "gmail", "googlemail", "gstatic", "googleapis"}),
    # Microsoft ecosystem
    frozenset({"microsoft", "outlook", "live", "hotmail", "office", "office365",
               "microsoftonline", "accountprotection"}),
    # Apple ecosystem
    frozenset({"apple", "icloud"}),
    # Meta ecosystem
    frozenset({"facebook", "instagram", "whatsapp", "meta"}),
    # Amazon ecosystem
    frozenset({"amazon", "amazonses", "awstrack"}),
    # GitHub / dev ecosystem (notifications contain URLs from any domain)
    frozenset({"github", "githubusercontent", "pytorch", "pypi"}),
]

# IPv4 pattern
IPV4_PATTERN = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}$"
)

# Redirect/click tracker script patterns in URL path
REDIRECT_SCRIPT_PATTERNS = re.compile(
    r"(?:/click\.php|/redirect\.php|/track\.php|/go\.php|/r\.php"
    r"|/redir|/click\?|/trk/|/track/|/out/|/bounce/|/deref/"
    r"|/public/click|/v\d+/public/click|/v\d+/click"
    r"|/c/l\?|/e/c\?|/wf/click"
    r"|/rd/[a-zA-Z0-9])",  # Short redirect path (/rd/xxxx)
    re.IGNORECASE,
)

# URL query parameter names commonly used for affiliate/spam tracking
AFFILIATE_SPAM_PARAMS = {
    "aff_id", "affiliate_id", "offer_id", "campaign_id", "click_id",
    "sub_id", "subid", "s1", "s2", "s3", "s4", "s5",
    "clickid", "affid", "pid", "oid", "tid",
}

# URL query parameter names that may contain encoded URLs
URL_CARRYING_PARAMS = {
    "u", "url", "link", "redirect", "goto", "dest", "destination",
    "target", "out", "redir", "ref", "return", "next", "continue",
}

# Email pattern for detecting email addresses in URL parameters
EMAIL_IN_URL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Common English vowels for entropy check
VOWELS = set("aeiouy")
CONSONANTS = set("bcdfghjklmnpqrstvwxz")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ExtractedUrl:
    """A URL extracted from an email body."""

    href: str
    display_text: str
    domain: str


@dataclass
class UrlAnalysisResult:
    """Result of URL analysis for a single email."""

    total_urls: int = 0
    suspicious_urls: list[dict] = field(default_factory=list)
    all_domains: list[str] = field(default_factory=list)
    has_suspicious: bool = False

    def to_prompt_text(self) -> str:
        """Format as text to inject into the LLM prompt."""
        if self.total_urls == 0:
            return "Aucun lien trouvé dans l'email."

        lines = [f"{self.total_urls} liens trouvés."]

        if not self.suspicious_urls:
            # Deduplicate domains for readability
            unique_domains = sorted(set(self.all_domains))
            lines.append(
                f"Domaines : {', '.join(unique_domains[:10])}."
            )
            lines.append("Aucune URL suspecte détectée.")
        else:
            lines.append(f"⚠ {len(self.suspicious_urls)} URL(s) SUSPECTE(S) :")
            for s in self.suspicious_urls:
                for reason in s["reasons"]:
                    lines.append(f"  - {reason}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_urls_from_html(html: str) -> list[ExtractedUrl]:
    """Extract all URLs from HTML email body with their display text."""
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        logger.warning("Failed to parse HTML for URL extraction")
        return []

    urls: list[ExtractedUrl] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        # Skip non-http links
        if not href.startswith(("http://", "https://")):
            if href.startswith(("mailto:", "tel:", "#")):
                continue
            continue

        display_text = a_tag.get_text(strip=True)
        domain = _extract_domain(href)

        urls.append(ExtractedUrl(
            href=href,
            display_text=display_text,
            domain=domain or "",
        ))

    return urls


def analyze_urls(
    urls: list[ExtractedUrl],
    sender_domain: str | None = None,
) -> UrlAnalysisResult:
    """Analyze extracted URLs for suspicious patterns.

    Checks applied:
      1. Display text shows a domain different from the actual href domain
      2. Homoglyphs in domain (Cyrillic chars mimicking Latin)
      3. URL shorteners in emails pretending to be from a known service
      4. IP address instead of domain
      5. Deceptive subdomains (legitimate domain as subdomain of malicious domain)
      6. Base64-encoded URLs hidden in query parameters
      7. Email address embedded in URL parameters (tracking/harvesting)
      8. Redirect/click tracker scripts (click.php, etc.)
      9. Suspicious random/gibberish domains (dfhv4y.com)
     10. Affiliate spam parameters (aff_id, offer_id, etc.)
     11. Sender domain mismatch (URLs point to unrelated domains)

    Args:
        urls: List of extracted URLs from the email body.
        sender_domain: Domain of the email sender (e.g., "mcdonalds.fr").
            Used for mismatch detection. Can be None.
    """
    result = UrlAnalysisResult(
        total_urls=len(urls),
        all_domains=[u.domain for u in urls if u.domain],
    )

    for url in urls:
        reasons: list[str] = []

        # 1. Display text ≠ actual URL domain
        display_domain = _extract_domain_from_text(url.display_text)
        if display_domain and url.domain:
            display_clean = display_domain.lower().removeprefix("www.")
            actual_clean = url.domain.lower().removeprefix("www.")
            if display_clean != actual_clean and not _is_tracking_redirect(url.domain):
                reasons.append(
                    f"Lien trompeur : affiche \"{display_domain}\" "
                    f"mais pointe vers \"{url.domain}\""
                )

        # 2. Homoglyphs in domain
        if url.domain:
            homoglyph_chars = _find_homoglyphs(url.domain)
            if homoglyph_chars:
                reasons.append(
                    f"Domaine avec caractères suspects (homoglyphes) : "
                    f"{url.domain} — caractères : {', '.join(homoglyph_chars)}"
                )

        # 3. URL shortener
        if url.domain and url.domain.lower() in SHORTENER_DOMAINS:
            reasons.append(
                f"Raccourcisseur d'URL ({url.domain}) — "
                f"masque la destination réelle"
            )

        # 4. IP address instead of domain (skip localhost/loopback)
        if url.domain and IPV4_PATTERN.match(url.domain):
            if not url.domain.startswith(("127.", "0.", "10.", "192.168.", "172.")):
                reasons.append(
                    f"URL pointant vers une adresse IP directe : {url.domain}"
                )

        # 5. Deceptive subdomain (paypal.com.evil.xyz)
        if url.domain:
            deceptive = _check_deceptive_subdomain(url.domain)
            if deceptive:
                reasons.append(deceptive)

        # ------------------------------------------------------------------
        # Phase 2: Enhanced fraud detection
        # ------------------------------------------------------------------

        # 6. Base64-encoded URLs in query parameters
        b64_findings = _check_base64_urls(url.href)
        reasons.extend(b64_findings)

        # 7. Email address embedded in URL parameters
        email_findings = _check_email_in_url(url.href)
        reasons.extend(email_findings)

        # 8. Redirect/click tracker script
        # Skip for sender's own tracking subdomains (e.g., mailing.github.com)
        if _is_redirect_script(url.href, sender_domain=sender_domain):
            reasons.append(
                f"Script de redirection/tracking détecté dans l'URL "
                f"({url.domain}) — masque la destination réelle"
            )

        # 9. Suspicious random/gibberish domain
        if url.domain:
            gibberish = _check_gibberish_domain(url.domain)
            if gibberish:
                reasons.append(gibberish)

        # 10. Affiliate spam parameters
        aff_findings = _check_affiliate_params(url.href)
        if aff_findings:
            reasons.append(aff_findings)

        # 10b. S3 bucket static hosting (common phishing technique)
        if url.domain:
            s3_finding = _check_s3_bucket_hosting(url.domain, url.href)
            if s3_finding:
                reasons.append(s3_finding)

        # 11. Sender domain mismatch — DISABLED
        # This heuristic generated too many false positives: legitimate emails
        # routinely contain links to third-party domains (partners, social media,
        # external services like escda.fr in Transavia emails). Real phishing is
        # already caught by brand impersonation detection (brand_detection.py)
        # which checks if the sender's display name impersonates a known brand.
        # The LLM also has enough context to judge domain mismatches.
        # Keeping the function for potential future use with stricter criteria.

        # 12. Suspicious long gibberish path (random token in URL path)
        # Skip for sender's own tracking subdomains (e.g., links.homeexchange.com)
        gibberish_path = _check_gibberish_path(url.href, sender_domain=sender_domain)
        if gibberish_path:
            reasons.append(gibberish_path)

        # Note: HTTP (no TLS) check removed — too many false positives.
        # Legitimate services (Facebook, Twitter, Google Maps, Fiverr,
        # Transavia) frequently use HTTP links in email footers.

        if reasons:
            result.suspicious_urls.append({
                "url": url.href[:200],
                "display_text": url.display_text[:100] if url.display_text else "",
                "domain": url.domain,
                "reasons": reasons,
            })

    result.has_suspicious = len(result.suspicious_urls) > 0
    return result


def analyze_email_urls(
    html: str | None,
    sender_domain: str | None = None,
) -> UrlAnalysisResult:
    """Full pipeline: extract URLs from HTML then analyze them.

    Args:
        html: HTML body of the email (can be None).
        sender_domain: Domain extracted from the sender's email address.
    """
    if not html:
        return UrlAnalysisResult()
    urls = extract_urls_from_html(html)
    return analyze_urls(urls, sender_domain=sender_domain)


# ---------------------------------------------------------------------------
# Phase 1 helpers (original)
# ---------------------------------------------------------------------------


def _extract_domain(url: str) -> str | None:
    """Extract domain from a full URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname
    except Exception:
        return None


def _extract_domain_from_text(text: str) -> str | None:
    """Try to extract a domain from display text (e.g., 'paypal.com' or 'www.paypal.com')."""
    if not text:
        return None
    text = text.strip()
    domain_pattern = re.compile(
        r"^(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)"
    )
    match = domain_pattern.match(text)
    if match:
        return match.group(1)
    return None


def _is_tracking_redirect(domain: str) -> bool:
    """Check if domain is a known email tracking/redirect service.

    Matching strategy:
    1. Exact match or subdomain of a known tracking domain
    2. Secure prefix match: prefix (click., track., etc.) + parent domain
       must ALSO be a known tracking domain. This prevents attackers from
       using "click.evil-phishing.xyz" to bypass all heuristics.
    """
    domain_lower = domain.lower()

    # Check if the domain or parent domain matches a known tracking service
    for tracking_domain in KNOWN_TRACKING_DOMAINS:
        if domain_lower == tracking_domain or domain_lower.endswith("." + tracking_domain):
            return True

    # Secure prefix matching: prefix MUST be paired with a verified parent
    # e.g., "click.sendgrid.net" -> prefix "click." + parent "sendgrid.net" (known) -> True
    # e.g., "click.evil-phishing.xyz" -> prefix "click." + parent unknown -> False
    for prefix in KNOWN_TRACKING_PREFIXES:
        if domain_lower.startswith(prefix):
            parent = domain_lower[len(prefix):]
            for tracking_domain in KNOWN_TRACKING_DOMAINS:
                if parent == tracking_domain or parent.endswith("." + tracking_domain):
                    return True

    return False


def _find_homoglyphs(domain: str) -> list[str]:
    """Find homoglyph characters in a domain name."""
    found = []
    for char in domain:
        if char in HOMOGLYPH_MAP:
            found.append(
                f"'{char}' (U+{ord(char):04X}, ressemble à '{HOMOGLYPH_MAP[char]}')"
            )
        elif ord(char) > 127:
            cat = unicodedata.category(char)
            if cat.startswith("L"):
                name = unicodedata.name(char, "UNKNOWN")
                found.append(f"'{char}' (U+{ord(char):04X}, {name})")
    return found


def _check_deceptive_subdomain(domain: str) -> str | None:
    """Check if a legitimate domain appears as a subdomain of a different domain.

    Example: paypal.com.evil.xyz -> 'paypal.com' is a subdomain of 'evil.xyz'

    Uses tldextract to correctly identify the registered domain, handling
    multi-part TLDs like .gouv.fr, .co.uk, etc.
    """
    try:
        extracted = _tld_extract(domain)
    except Exception:
        return None

    if not extracted.domain or not extracted.suffix:
        return None

    real_domain = f"{extracted.domain}.{extracted.suffix}"
    subdomain = extracted.subdomain

    # No subdomain → nothing to check
    if not subdomain:
        return None

    for legit in COMMON_LEGITIMATE_DOMAINS:
        legit_main = legit.split(".")[0]  # e.g., "paypal" from "paypal.com"

        if legit_main in subdomain and real_domain != legit:
            return (
                f"Sous-domaine trompeur : \"{domain}\" utilise "
                f"\"{legit}\" comme sous-domaine mais le vrai domaine est \"{real_domain}\""
            )

    return None


# ---------------------------------------------------------------------------
# Phase 2 helpers (enhanced fraud detection)
# ---------------------------------------------------------------------------


def _check_base64_urls(href: str) -> list[str]:
    """Detect and decode base64-encoded URLs hidden in query parameters.

    Spammers encode the real destination URL in base64 inside a redirect URL.
    Example: click.php?u=aHR0cHM6Ly9kZmh2NHkuY29tLw== -> https://dfhv4y.com/

    Returns list of reason strings (empty if clean).
    """
    reasons: list[str] = []
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query, keep_blank_values=True)
    except Exception:
        return reasons

    for param_name, values in params.items():
        for value in values:
            if not value or len(value) < 16:
                # Too short to be a meaningful base64-encoded URL
                continue

            # Check if it looks like base64 (alphanumeric + / + = padding)
            # Base64 strings are typically longer and have specific patterns
            cleaned = value.strip()
            if not re.match(r"^[A-Za-z0-9+/=_-]+$", cleaned):
                continue

            # Try to decode
            decoded_url = _try_decode_base64(cleaned)
            if decoded_url and decoded_url.startswith(("http://", "https://")):
                decoded_domain = _extract_domain(decoded_url)
                detail = f"\"{decoded_domain}\"" if decoded_domain else f"\"{decoded_url[:60]}\""

                reasons.append(
                    f"URL encodée en base64 dans le paramètre '{param_name}' — "
                    f"destination cachée : {detail}"
                )

                # Additionally check if the decoded destination itself is suspicious
                if decoded_domain:
                    gibberish = _check_gibberish_domain(decoded_domain)
                    if gibberish:
                        reasons.append(
                            f"La destination décodée a un domaine suspect : {gibberish}"
                        )

                    # Check for affiliate params in decoded URL
                    aff = _check_affiliate_params(decoded_url)
                    if aff:
                        reasons.append(
                            f"La destination décodée contient des paramètres d'affiliation spam : {aff}"
                        )

    return reasons


def _try_decode_base64(value: str) -> str | None:
    """Try to decode a base64 string. Returns decoded string or None."""
    # Try standard base64
    for v in [value, value + "=", value + "=="]:
        try:
            decoded = base64.b64decode(v, validate=True).decode("utf-8", errors="strict")
            # Must look like a URL to be considered
            if decoded.startswith(("http://", "https://", "www.")):
                return decoded
        except Exception:
            continue

    # Try URL-safe base64
    for v in [value, value + "=", value + "=="]:
        try:
            decoded = base64.urlsafe_b64decode(v).decode("utf-8", errors="strict")
            if decoded.startswith(("http://", "https://", "www.")):
                return decoded
        except Exception:
            continue

    return None


def _check_email_in_url(href: str) -> list[str]:
    """Detect email addresses embedded in URL query parameters.

    Spammers include the recipient's email in URL parameters for tracking
    and to confirm the address is active.
    Example: click.php?e=hello@leodurand.com

    Returns list of reason strings (empty if clean).
    """
    reasons: list[str] = []
    try:
        parsed = urlparse(href)
        # Check query string for email addresses
        query = parsed.query
        if not query:
            return reasons

        emails_found = EMAIL_IN_URL_PATTERN.findall(query)
        if emails_found:
            # Filter out obvious false positives (e.g., example.com in documentation URLs)
            real_emails = [
                e for e in emails_found
                if not e.endswith(("@example.com", "@example.org", "@test.com"))
            ]
            if real_emails:
                masked = [_mask_email(e) for e in real_emails]
                reasons.append(
                    f"Adresse email intégrée dans l'URL ({', '.join(masked)}) — "
                    f"tracking/confirmation d'adresse active"
                )
    except Exception:
        pass

    return reasons


def _mask_email(email: str) -> str:
    """Mask an email for display: hello@leodurand.com -> h***o@l***d.com"""
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "***"
        else:
            masked_local = local[0] + "***" + local[-1]

        domain_parts = domain.split(".")
        if len(domain_parts) >= 2:
            d = domain_parts[0]
            if len(d) <= 2:
                masked_domain = d[0] + "***"
            else:
                masked_domain = d[0] + "***" + d[-1]
            masked_domain += "." + ".".join(domain_parts[1:])
        else:
            masked_domain = domain

        return f"{masked_local}@{masked_domain}"
    except Exception:
        return "***@***"


def _is_redirect_script(href: str, sender_domain: str | None = None) -> bool:
    """Check if the URL path contains redirect/click tracking script patterns.

    Examples:
    - https://tracemail.enima.online/v2/public/click.php?...
    - https://evil.com/redirect.php?url=...
    - https://track.example.com/click?id=...

    Excludes:
    - Known legitimate tracking services (Mailchimp, SendGrid, etc.)
    - Sender's own tracking subdomains (mailing.github.com for github.com,
      links.homeexchange.com for homeexchange.com, etc.)
    """
    domain = _extract_domain(href)

    # Don't flag known legitimate tracking services
    if domain and _is_tracking_redirect(domain):
        return False

    # Don't flag sender's own tracking subdomains
    # e.g., mailing.github.com is legitimate for sender github.com
    if domain and sender_domain:
        url_core = _extract_core_domain(domain)
        sender_core = _extract_core_domain(sender_domain)
        if url_core and sender_core and url_core == sender_core:
            return False

    try:
        parsed = urlparse(href)
        path = parsed.path.lower()

        # Check URL path for redirect script patterns
        if REDIRECT_SCRIPT_PATTERNS.search(href.lower()):
            return True

        # Also check for generic redirect patterns in the path
        # Only flag if the domain itself is unknown/suspicious
        if path.endswith((".php", ".asp", ".aspx")):
            path_parts = path.rsplit("/", 1)[-1].lower()
            if any(kw in path_parts for kw in ("click", "track", "redirect", "redir", "go", "out")):
                return True

    except Exception:
        pass

    return False


def _check_gibberish_domain(domain: str) -> str | None:
    """Detect suspicious random/gibberish domains.

    Spammers use randomly generated short domains like:
    - dfhv4y.com
    - xk9mw2.net
    - abc123z.xyz

    We use multiple signals:
    - High consonant-to-vowel ratio
    - Mixing of digits and letters
    - Very short or unusual domain names
    - Shannon entropy (randomness measure)

    Returns a reason string or None if domain looks normal.
    """
    if not domain:
        return None

    # Skip known tracking/CDN domains
    if _is_tracking_redirect(domain):
        return None

    # Extract the registered domain name using tldextract (PSL-based).
    # For "zwd8wbyj.r.eu-central-1.awstrack.me" -> main = "awstrack"
    # For "dfhv4y.com" -> main = "dfhv4y"
    # For "example.co.uk" -> main = "example"
    # For "dgfip.finances.gouv.fr" -> main = "finances"
    try:
        extracted = _tld_extract(domain)
        main = extracted.domain
    except Exception:
        return None

    if not main:
        return None

    # Skip very common/short domains that are legitimate
    if len(main) <= 2:
        return None

    # Skip domains that are just common words or well-known brands
    # (rough heuristic - if it's all vowels+consonants in natural pattern)
    if len(main) > 15:
        # Long domains are less likely to be random gibberish
        return None

    # --- Signal 1: Character mixing (digits + letters) ---
    has_digits = any(c.isdigit() for c in main)
    has_letters = any(c.isalpha() for c in main)
    digit_count = sum(1 for c in main if c.isdigit())

    # A domain with mixed digits and letters where digits aren't just a
    # version number (e.g., "web2" is ok, "dfhv4y" is suspicious)
    mixed_suspicious = (
        has_digits and has_letters
        and digit_count >= 1
        and len(main) <= 8
        and not main.endswith(("24", "365", "360", "247"))  # common suffixes
    )

    # --- Signal 2: Consonant/vowel ratio ---
    letters_only = [c for c in main if c.isalpha()]
    if letters_only:
        vowel_count = sum(1 for c in letters_only if c in VOWELS)
        consonant_count = sum(1 for c in letters_only if c in CONSONANTS)
        vowel_ratio = vowel_count / len(letters_only) if letters_only else 0.5

        # Natural English/French words have ~35-45% vowels
        # Gibberish strings tend to have very few vowels (< 22%)
        # or almost all vowels (> 80%)
        unnatural_ratio = vowel_ratio < 0.22 or vowel_ratio > 0.80
    else:
        unnatural_ratio = False
        vowel_ratio = 0.5

    # --- Signal 3: Shannon entropy ---
    entropy = _shannon_entropy(main)
    # Random strings typically have entropy > 3.0 for short strings
    # Natural words have lower entropy (more letter repetition/patterns)
    high_entropy = entropy > 3.2 and len(main) <= 10

    # --- Decision: combine signals ---
    # Need at least 2 signals to flag as suspicious to avoid false positives
    signals = sum([mixed_suspicious, unnatural_ratio, high_entropy])

    if signals >= 2:
        return (
            f"Domaine suspect (possiblement généré aléatoirement) : "
            f"\"{domain}\" — nom de domaine inhabituel"
        )

    return None


def _shannon_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string (measure of randomness).

    Higher entropy = more random. Natural language words typically
    have entropy < 3.0, while random strings have entropy > 3.5.
    """
    if not text:
        return 0.0

    freq = Counter(text)
    length = len(text)
    entropy = 0.0

    for count in freq.values():
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)

    return entropy


def _check_affiliate_params(href: str) -> str | None:
    """Detect affiliate/spam tracking parameters in URL.

    Spam emails often contain URLs with affiliate tracking parameters
    like aff_id, offer_id, sub_id, etc. These are strong indicators
    of unsolicited commercial email or scam affiliate programs.

    Returns a reason string or None.
    """
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query, keep_blank_values=True)
    except Exception:
        return None

    found_params = []
    for param_name in params:
        if param_name.lower() in AFFILIATE_SPAM_PARAMS:
            found_params.append(param_name)

    # Need at least 2 affiliate params to flag (single ones could be coincidence)
    if len(found_params) >= 2:
        return (
            f"Paramètres d'affiliation/spam dans l'URL : "
            f"{', '.join(found_params[:5])}"
        )

    return None


def _check_s3_bucket_hosting(domain: str, href: str) -> str | None:
    """Detect AWS S3 bucket static hosting used for phishing pages.

    Phishers commonly host pages on S3 buckets like:
    - managed-marketplace-endpoint-a8.s3.us-west-1.amazonaws.com/7BK2nxC46
    - business-transfer-2020.s3.us-west-2.amazonaws.com/WjTGTJJStSP6j

    These are NOT the same as S3-backed CDN/tracking services. The pattern
    is specifically: <bucket-name>.s3.<region>.amazonaws.com or
    s3.<region>.amazonaws.com/<bucket-name>.

    Returns a reason string or None.
    """
    domain_lower = domain.lower()

    # Match S3 bucket hosting patterns
    # Pattern 1: <bucket>.s3.<region>.amazonaws.com
    # Pattern 2: <bucket>.s3.amazonaws.com
    # Pattern 3: s3.<region>.amazonaws.com/<bucket>
    s3_patterns = [
        re.compile(r"\.s3[\.-][a-z0-9-]*\.?amazonaws\.com$"),
        re.compile(r"^s3[\.-][a-z0-9-]*\.?amazonaws\.com$"),
    ]

    for pattern in s3_patterns:
        if pattern.search(domain_lower):
            return (
                f"URL hébergée sur un bucket S3 AWS ({domain}) — "
                f"technique courante de phishing pour héberger des pages frauduleuses"
            )

    return None


def _are_related_domains(url_domain: str, sender_domain: str) -> bool:
    """Check if URL and sender domains belong to the same organization group.

    Uses RELATED_DOMAIN_GROUPS to identify domains that legitimately
    cross-link, such as urssaf.fr linking to net-entreprises.fr.
    """
    url_core = _extract_core_domain(url_domain)
    sender_core = _extract_core_domain(sender_domain)
    if not url_core or not sender_core:
        return False

    for group in RELATED_DOMAIN_GROUPS:
        if url_core in group and sender_core in group:
            return True

    return False


def _check_sender_domain_mismatch(
    url_domain: str,
    sender_domain: str,
) -> str | None:
    """Check if a URL's domain is completely unrelated to the sender's domain.

    This detects cases where an email claims to be from "service@legit.com"
    but contains links pointing to "tracemail.enima.online" or "dfhv4y.com".

    Legitimate exceptions:
    - Known tracking/redirect services (Mailchimp, SendGrid, etc.)
    - CDN/image hosting domains (cloudfront, cloudinary, etc.)
    - Common third-party services (googleapis, gstatic, etc.)
    - Personal/webmail senders (gmail, outlook, etc.) — people forward content
    - Related domain groups (e.g., urssaf.fr ↔ net-entreprises.fr)

    Returns a reason string or None.
    """
    url_lower = url_domain.lower()
    sender_lower = sender_domain.lower()

    # -----------------------------------------------------------------------
    # Skip entirely for personal/webmail sender domains.
    # People send forwards, share links, etc. — URL mismatches are expected.
    # -----------------------------------------------------------------------
    sender_core = _extract_core_domain(sender_lower)
    if sender_core and sender_core in PERSONAL_WEBMAIL_DOMAINS:
        return None

    # Don't flag private/loopback IP addresses (common in dev content, GitHub issues)
    if IPV4_PATTERN.match(url_lower) and url_lower.startswith(
        ("127.", "0.", "10.", "192.168.", "172.")
    ):
        return None

    # Don't flag if URL domain is a known tracking service
    if _is_tracking_redirect(url_lower):
        return None

    # Don't flag common CDN / static asset / auth / social domains
    safe_third_party = {
        "cloudfront.net", "cloudinary.com", "googleapis.com", "gstatic.com",
        "googleusercontent.com", "gravatar.com", "wp.com", "imgur.com",
        "fbcdn.net", "twimg.com", "akamaized.net", "fastly.net",
        "cloudflare.com", "cdn.jsdelivr.net", "unpkg.com",
        "recaptcha.net", "hcaptcha.com",
        # Social login / OAuth
        "accounts.google.com", "login.microsoftonline.com",
        "appleid.apple.com", "facebook.com",
        # Microsoft URL shortener + services
        "aka.ms", "office.com", "sharepoint.com",
        "safelinks.protection.outlook.com",
        # Apple ecosystem (broad — covers itunes, developer, support, etc.)
        "apple.com",
        # WhatsApp / Meta
        "whatsapp.com",
        # Common newsletter / content link targets
        "youtube.com", "youtu.be", "medium.com", "substack.com",
        "wordpress.com", "github.com", "gitlab.com", "bitbucket.org",
        "stackoverflow.com", "reddit.com", "x.com", "twitter.com",
        "linkedin.com", "instagram.com", "pinterest.com", "tiktok.com",
        "vimeo.com", "dailymotion.com", "figma.com", "notion.so",
        "docs.google.com", "drive.google.com", "forms.google.com",
        "maps.google.com", "play.google.com",
        # App stores
        "apps.apple.com", "itunes.apple.com",
        # Survey / feedback platforms
        "surveymonkey.com", "typeform.com", "google.com",
        # Communication platforms
        "slack.com", "discord.com", "zoom.us", "teams.microsoft.com",
        # French services
        "doctolib.fr", "blablacar.fr", "blablacar.com",
    }
    for safe in safe_third_party:
        if url_lower == safe or url_lower.endswith("." + safe):
            return None

    # -----------------------------------------------------------------------
    # Check related domain groups — organizations that legitimately
    # cross-link between their different domains.
    # -----------------------------------------------------------------------
    if _are_related_domains(url_lower, sender_lower):
        return None

    # Extract "core" domain parts for comparison
    # e.g., "notifications.homeexchange.com" -> "homeexchange"
    # e.g., "hello@notice.xiaomi.com" -> "xiaomi"
    url_core = _extract_core_domain(url_lower)

    if not url_core or not sender_core:
        return None

    # If the core domains share a common root, they're likely related
    if url_core == sender_core:
        return None

    # Check if one contains the other (e.g., "mcdo" in "mcdonalds")
    if url_core in sender_core or sender_core in url_core:
        return None

    # The domains are truly unrelated — flag as suspicious.
    # Known tracking services and CDNs are already excluded above.
    return (
        f"Domaine de l'URL ({url_domain}) sans rapport avec "
        f"le domaine de l'expéditeur ({sender_domain})"
    )


def _extract_core_domain(domain: str) -> str | None:
    """Extract the core/brand part of a domain using tldextract (PSL-based).

    Examples:
    - "tracemail.enima.online" -> "enima"
    - "notifications.homeexchange.com" -> "homeexchange"
    - "dfhv4y.com" -> "dfhv4y"
    - "example.co.uk" -> "example"
    - "dgfip.finances.gouv.fr" -> "finances"
    """
    if not domain:
        return None
    try:
        extracted = _tld_extract(domain)
        return extracted.domain or None
    except Exception:
        return None


def _check_gibberish_path(href: str, sender_domain: str | None = None) -> str | None:
    """Detect URLs with suspiciously long random/gibberish path segments.

    Phishing and spam URLs frequently use long random tokens in the path:
    - http://serviice.casacam.net/rd/4lBwjm6146jMFT1083jrtdqxitlf...
    - https://evil.com/track/aB3xK9mW2pQ7nL4yH8vJ6tR1oU5iE0sD

    Legitimate URLs can have long paths, but they follow recognizable patterns
    (UUIDs, base64 IDs, slug-words). Pure mixed-case alphanumeric gibberish
    of significant length is a strong phishing signal.

    Skips:
    - Known tracking/redirect services (awstrack.me, sendgrid.net)
    - Sender's own tracking subdomains (links.homeexchange.com for
      homeexchange.com sender) — services use their own subdomains
      for click tracking with long tokens.

    Returns a reason string or None.
    """
    try:
        parsed = urlparse(href)
        path = parsed.path
        domain = parsed.hostname
    except Exception:
        return None

    if not path or path == "/":
        return None

    # Known tracking services use long tokens in their paths — that's normal
    if domain and _is_tracking_redirect(domain):
        return None

    # Sender's own tracking subdomains also use long tokens — that's normal
    # e.g., links.homeexchange.com for sender info.homeexchange.com
    if domain and sender_domain:
        url_core = _extract_core_domain(domain)
        sender_core = _extract_core_domain(sender_domain)
        if url_core and sender_core and url_core == sender_core:
            return None

    # Check each path segment
    segments = [s for s in path.split("/") if s]
    for segment in segments:
        # Skip short segments (normal path components like "rd", "api", "v2")
        if len(segment) < 25:
            continue

        # Count character types
        has_upper = any(c.isupper() for c in segment)
        has_lower = any(c.islower() for c in segment)
        has_digit = any(c.isdigit() for c in segment)
        letter_count = sum(1 for c in segment if c.isalpha())
        digit_count = sum(1 for c in segment if c.isdigit())

        # Mixed case + digits in a long segment = likely random token
        if has_upper and has_lower and has_digit and letter_count > 5 and digit_count > 2:
            # Exclude common patterns: UUIDs (contain dashes), base64 (contain =+/)
            if "-" not in segment and "=" not in segment:
                return (
                    f"URL avec chemin suspect (jeton aléatoire long) : "
                    f"le chemin contient une chaîne aléatoire de {len(segment)} caractères"
                )

    return None



# _check_no_tls removed — too many false positives.
# Legitimate services (Facebook, Twitter, LinkedIn, Google Maps, Transavia,
# Fiverr, Pinterest) frequently use HTTP links in email footers/signatures.
# This heuristic alone generated enough "suspicious" URLs (2+) to trigger
# structural phishing detection on perfectly legitimate emails.
