"""Brand impersonation detection for phishing emails.

Compares the sender display name against a database of known brands
and their legitimate sending domains. Detects cases like:
  - Display name "EDF" but sender domain "espacionewen.cl"
  - Display name "PayPal" but sender domain "random-domain.xyz"

This is a structural, pre-LLM check that provides a strong signal
for phishing detection even when the LLM fails or is unavailable.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Brand database: {keyword: [legitimate domains]}
#
# Keywords are matched against the sender display name (case-insensitive).
# Domains include all legitimate sending domains for that brand
# (including subdomains like notice.xiaomi.com → xiaomi.com).
# ---------------------------------------------------------------------------

BRAND_DATABASE: dict[str, list[str]] = {
    # --- French energy / utilities ---
    "edf": ["edf.fr", "edf.com"],
    "engie": ["engie.fr", "engie.com"],
    "totalenergies": ["totalenergies.fr", "totalenergies.com"],

    # --- French government / public services ---
    "ameli": ["ameli.fr", "assurance-maladie.fr"],
    "impots": ["impots.gouv.fr", "dgfip.finances.gouv.fr"],
    "caf": ["caf.fr", "cnaf.fr"],
    "pole emploi": ["pole-emploi.fr", "francetravail.fr"],
    "france travail": ["pole-emploi.fr", "francetravail.fr"],
    "cpam": ["ameli.fr", "assurance-maladie.fr"],
    "ants": ["ants.gouv.fr"],
    "antai": ["antai.gouv.fr"],

    # --- French banks ---
    "banque postale": ["labanquepostale.fr"],
    "la banque postale": ["labanquepostale.fr"],
    "credit agricole": ["credit-agricole.fr", "ca-group.com"],
    "crédit agricole": ["credit-agricole.fr", "ca-group.com"],
    "bnp paribas": ["bnpparibas.fr", "bnpparibas.com", "bnpparibas.net"],
    "bnp": ["bnpparibas.fr", "bnpparibas.com", "bnpparibas.net"],
    "societe generale": ["societegenerale.fr", "socgen.com"],
    "société générale": ["societegenerale.fr", "socgen.com"],
    "lcl": ["lcl.fr"],
    "boursorama": ["boursorama.fr", "boursobank.com"],
    "boursobank": ["boursorama.fr", "boursobank.com"],
    "caisse d'epargne": ["caisse-epargne.fr"],
    "caisse d'épargne": ["caisse-epargne.fr"],
    "credit mutuel": ["creditmutuel.fr"],
    "crédit mutuel": ["creditmutuel.fr"],

    # --- French telecom ---
    "orange": ["orange.fr", "orange.com"],
    "sfr": ["sfr.fr", "sfr.com"],
    "free": ["free.fr", "free-mobile.fr", "iliad.fr"],
    "bouygues telecom": ["bouyguestelecom.fr"],

    # --- French postal / delivery ---
    "la poste": ["laposte.fr", "laposte.net", "colissimo.fr", "notif-colissimo-laposte.info"],
    "colissimo": ["laposte.fr", "colissimo.fr", "notif-colissimo-laposte.info"],
    "chronopost": ["chronopost.fr"],

    # --- International tech ---
    "paypal": ["paypal.com", "paypal.fr"],
    "amazon": ["amazon.fr", "amazon.com", "amazon.de", "amazon.co.uk", "amazonses.com"],
    "apple": ["apple.com", "icloud.com"],
    "microsoft": ["microsoft.com", "outlook.com", "live.com", "hotmail.com"],
    "google": ["google.com", "google.fr", "gmail.com", "googlemail.com"],
    "netflix": ["netflix.com"],
    "spotify": ["spotify.com"],
    "facebook": ["facebook.com", "facebookmail.com", "meta.com"],
    "instagram": ["instagram.com", "facebookmail.com"],
    "whatsapp": ["whatsapp.com", "facebookmail.com"],
    "linkedin": ["linkedin.com"],
    "twitter": ["twitter.com", "x.com"],

    # --- E-commerce ---
    "cdiscount": ["cdiscount.com"],
    "fnac": ["fnac.com", "fnacspectacles.com", "fnacdarty.com"],
    "darty": ["darty.com", "fnacdarty.com"],
    "leboncoin": ["leboncoin.fr"],
    "vinted": ["vinted.fr", "vinted.com"],

    # --- Shipping ---
    "dhl": ["dhl.com", "dhl.fr", "dhl.de"],
    "ups": ["ups.com"],
    "fedex": ["fedex.com"],
    "mondial relay": ["mondialrelay.fr"],

    # --- German / European retail & brands ---
    "bauhaus": ["bauhaus.info", "bauhaus.de", "bauhaus.at", "bauhaus.ch"],
    "lidl": ["lidl.de", "lidl.fr", "lidl.com"],
    "aldi": ["aldi.de", "aldi.fr", "aldi.com", "aldi-sued.de", "aldi-nord.de"],
    "mediamarkt": ["mediamarkt.de", "mediamarkt.fr"],
    "saturn": ["saturn.de"],
    "otto": ["otto.de"],
    "zalando": ["zalando.de", "zalando.fr", "zalando.com"],
    "dm": ["dm.de"],

    # --- German banks ---
    "sparkasse": ["sparkasse.de"],
    "deutsche bank": ["deutsche-bank.de", "db.com"],
    "commerzbank": ["commerzbank.de"],
    "volksbank": ["volksbank.de"],
    "postbank": ["postbank.de"],
    "ing": ["ing.de", "ing.com"],
    "n26": ["n26.com"],

    # --- German telecom ---
    "telekom": ["telekom.de", "t-online.de"],
    "vodafone": ["vodafone.de", "vodafone.com"],
    "o2": ["o2online.de"],

    # --- German government / services ---
    "elster": ["elster.de"],
    "bundesagentur": ["arbeitsagentur.de"],
}

# Characters to strip from display names before matching
_STRIP_CHARS = re.compile(r"[&@#!?*+_\-.,;:'\"/\\()\[\]{}|<>~`^$%0-9]")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BrandCheckResult:
    """Result of brand impersonation check."""

    is_impersonation: bool = False
    claimed_brand: str | None = None
    expected_domains: list[str] = field(default_factory=list)
    actual_domain: str | None = None

    def to_prompt_text(self) -> str:
        """Format as text to inject into the LLM prompt."""
        if not self.is_impersonation:
            return ""

        return (
            f"⚠ USURPATION D'IDENTITÉ DÉTECTÉE : "
            f"le nom d'expéditeur mentionne « {self.claimed_brand} » "
            f"mais le domaine réel est « {self.actual_domain} ». "
            f"Les domaines légitimes de {self.claimed_brand} sont : "
            f"{', '.join(self.expected_domains)}."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_brand_impersonation(
    from_name: str | None,
    from_address: str,
) -> BrandCheckResult:
    """Check if the sender display name impersonates a known brand.

    Compares the display name against the brand database and checks
    if the sender's email domain matches any legitimate domain for
    the claimed brand.

    Also detects fake domains in the email local part, e.g.:
      Bauhaus-Marktforschung.de@namolixos.info

    Args:
        from_name: Sender display name (e.g., "edf&vous").
        from_address: Sender email address (e.g., "edf@espacionewen.cl").

    Returns:
        BrandCheckResult with impersonation details if detected.
    """
    if not from_name or not from_address:
        return BrandCheckResult()

    # Extract domain from email address
    if "@" not in from_address:
        return BrandCheckResult()
    local_part = from_address.rsplit("@", 1)[0].lower()
    actual_domain = from_address.rsplit("@", 1)[1].lower()

    # Normalize display name: lowercase, strip special characters
    cleaned_name = _STRIP_CHARS.sub(" ", from_name.lower()).strip()
    # Collapse multiple spaces
    cleaned_name = re.sub(r"\s+", " ", cleaned_name)

    # Check each brand keyword against the cleaned display name
    for keyword, legitimate_domains in BRAND_DATABASE.items():
        if not _keyword_matches(keyword, cleaned_name):
            continue

        # Brand keyword found in display name — check if domain is legitimate
        if _domain_is_legitimate(actual_domain, legitimate_domains):
            continue

        # Brand mentioned but domain doesn't match → impersonation
        logger.info(
            "Brand impersonation detected: display name '%s' matches brand '%s' "
            "but domain '%s' is not in legitimate domains %s",
            from_name, keyword, actual_domain, legitimate_domains,
        )
        return BrandCheckResult(
            is_impersonation=True,
            claimed_brand=keyword,
            expected_domains=legitimate_domains,
            actual_domain=actual_domain,
        )

    # --- Check for fake domain in email local part ---
    # Pattern: "Brand-Something.tld@attacker-domain.org"
    # The local part mimics a domain to appear legitimate.
    fake_domain_result = _check_fake_domain_in_local_part(
        local_part, actual_domain, from_name
    )
    if fake_domain_result:
        return fake_domain_result

    return BrandCheckResult()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _keyword_matches(keyword: str, cleaned_name: str) -> bool:
    """Check if a brand keyword matches in the cleaned display name.

    Uses word boundary matching to avoid false positives:
    - "edf" matches "edf", "edf vous", "edf&vous" (after cleaning: "edf vous")
    - "free" matches "free", "free mobile" but NOT "carefree" or "freestyle"
    """
    # For single-word keywords, use word boundary regex
    # For multi-word keywords (e.g., "credit agricole"), check substring
    if " " in keyword:
        return keyword in cleaned_name

    # Word boundary match for single-word keywords
    pattern = rf"\b{re.escape(keyword)}\b"
    return bool(re.search(pattern, cleaned_name))


def _check_fake_domain_in_local_part(
    local_part: str, actual_domain: str, from_name: str
) -> BrandCheckResult | None:
    """Detect fake domain names embedded in the email local part.

    Common phishing pattern:
      Bauhaus-Marktforschung.de@namolixos.info
      Paypal-auszahlungsabteilung.com@ewartista.org

    The local part (before @) looks like a domain name (contains a TLD suffix)
    but the actual sending domain is completely unrelated.
    """
    # Check if local part ends with what looks like a TLD (.com, .de, .fr, etc.)
    tld_pattern = re.compile(
        r".*\.(?:com|net|org|de|fr|uk|it|es|nl|be|ch|at|info|biz|io|co|eu)$"
    )
    if not tld_pattern.match(local_part):
        return None

    # The local part looks like a domain. Extract the "fake domain" part
    # e.g., "Bauhaus-Marktforschung.de" or "Paypal-auszahlungsabteilung.com"
    fake_domain = local_part

    # Check if the fake domain matches any brand keyword
    fake_domain_cleaned = _STRIP_CHARS.sub(" ", fake_domain).strip()
    fake_domain_cleaned = re.sub(r"\s+", " ", fake_domain_cleaned)

    for keyword, legitimate_domains in BRAND_DATABASE.items():
        if _keyword_matches(keyword, fake_domain_cleaned):
            logger.info(
                "Fake domain in local part: '%s' mimics brand '%s', "
                "actual domain is '%s'",
                local_part, keyword, actual_domain,
            )
            return BrandCheckResult(
                is_impersonation=True,
                claimed_brand=keyword,
                expected_domains=legitimate_domains,
                actual_domain=actual_domain,
            )

    # Even without a brand match, a fake domain in the local part is inherently
    # suspicious — flag it as impersonation with generic brand info
    logger.info(
        "Fake domain pattern in local part: '%s@%s' — "
        "local part mimics a domain name",
        local_part, actual_domain,
    )
    return BrandCheckResult(
        is_impersonation=True,
        claimed_brand=fake_domain,
        expected_domains=[fake_domain],
        actual_domain=actual_domain,
    )


def _domain_is_legitimate(
    actual_domain: str,
    legitimate_domains: list[str],
) -> bool:
    """Check if the actual sending domain matches any legitimate domain.

    Handles:
    - Exact matches: edf.fr == edf.fr
    - Subdomains: notice.xiaomi.com matches xiaomi.com

    Note: brand+suffix matching (e.g., fnacspectacles.com for "fnac") is NOT
    done generically because it would also match phishing domains like
    paypal-verify.xyz. Instead, known brand variants are listed explicitly
    in BRAND_DATABASE (e.g., fnac → [fnac.com, fnacspectacles.com]).
    """
    for legit in legitimate_domains:
        if actual_domain == legit:
            return True
        # Allow subdomains (e.g., mail.edf.fr matches edf.fr)
        if actual_domain.endswith("." + legit):
            return True

    return False
