"""Tests for brand impersonation detection — pure functions."""

from app.services.brand_detection import (
    BrandCheckResult,
    _domain_is_legitimate,
    _keyword_matches,
    check_brand_impersonation,
)

# ---------------------------------------------------------------------------
# check_brand_impersonation
# ---------------------------------------------------------------------------


class TestCheckBrandImpersonation:
    """Test the main brand impersonation detection function."""

    def test_edf_impersonation(self):
        """The exact case from the reported phishing email."""
        result = check_brand_impersonation(
            from_name="edf&vous",
            from_address="edf@espacionewen.cl",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "edf"
        assert "edf.fr" in result.expected_domains
        assert result.actual_domain == "espacionewen.cl"

    def test_edf_legitimate(self):
        """Real EDF emails should not be flagged."""
        result = check_brand_impersonation(
            from_name="EDF & Vous",
            from_address="noreply@edf.fr",
        )
        assert result.is_impersonation is False

    def test_edf_subdomain_legitimate(self):
        """Subdomains of legitimate domains should not be flagged."""
        result = check_brand_impersonation(
            from_name="EDF",
            from_address="notifications@mail.edf.fr",
        )
        assert result.is_impersonation is False

    def test_paypal_impersonation(self):
        result = check_brand_impersonation(
            from_name="PayPal",
            from_address="security@paypal-verify.xyz",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "paypal"

    def test_paypal_legitimate(self):
        result = check_brand_impersonation(
            from_name="PayPal",
            from_address="service@paypal.com",
        )
        assert result.is_impersonation is False

    def test_banque_postale_impersonation(self):
        result = check_brand_impersonation(
            from_name="La Banque Postale",
            from_address="support@secure-banquepostale.com",
        )
        assert result.is_impersonation is True
        assert "banque postale" in result.claimed_brand

    def test_ameli_impersonation(self):
        result = check_brand_impersonation(
            from_name="Ameli.fr - Assurance Maladie",
            from_address="remboursement@ameli-sante.xyz",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "ameli"

    def test_ameli_legitimate(self):
        result = check_brand_impersonation(
            from_name="Ameli",
            from_address="ne-pas-repondre@ameli.fr",
        )
        assert result.is_impersonation is False

    def test_no_brand_match(self):
        """Unknown sender names should not be flagged."""
        result = check_brand_impersonation(
            from_name="John Doe",
            from_address="john@company.com",
        )
        assert result.is_impersonation is False

    def test_empty_from_name(self):
        result = check_brand_impersonation(
            from_name="",
            from_address="test@example.com",
        )
        assert result.is_impersonation is False

    def test_none_from_name(self):
        result = check_brand_impersonation(
            from_name=None,
            from_address="test@example.com",
        )
        assert result.is_impersonation is False

    def test_empty_from_address(self):
        result = check_brand_impersonation(
            from_name="EDF",
            from_address="",
        )
        assert result.is_impersonation is False

    def test_credit_agricole_impersonation(self):
        result = check_brand_impersonation(
            from_name="Crédit Agricole",
            from_address="alerte@credit-agricole-securite.net",
        )
        assert result.is_impersonation is True

    def test_amazon_legitimate(self):
        result = check_brand_impersonation(
            from_name="Amazon.fr",
            from_address="ship-confirm@amazon.fr",
        )
        assert result.is_impersonation is False

    def test_netflix_impersonation(self):
        result = check_brand_impersonation(
            from_name="Netflix",
            from_address="billing@netflix-renew.com",
        )
        assert result.is_impersonation is True

    def test_orange_legitimate(self):
        result = check_brand_impersonation(
            from_name="Orange",
            from_address="noreply@orange.fr",
        )
        assert result.is_impersonation is False


# ---------------------------------------------------------------------------
# _keyword_matches
# ---------------------------------------------------------------------------


class TestKeywordMatches:
    def test_exact_match(self):
        assert _keyword_matches("edf", "edf") is True

    def test_word_boundary(self):
        assert _keyword_matches("edf", "edf vous") is True

    def test_no_partial_match(self):
        """'free' should not match in 'carefree'."""
        assert _keyword_matches("free", "carefree") is False

    def test_no_partial_match_prefix(self):
        """'free' should not match in 'freestyle'."""
        assert _keyword_matches("free", "freestyle") is False

    def test_free_standalone(self):
        assert _keyword_matches("free", "free mobile") is True

    def test_multi_word_keyword(self):
        assert _keyword_matches("credit agricole", "credit agricole alerte") is True

    def test_multi_word_no_match(self):
        assert _keyword_matches("credit agricole", "credit lyonnais") is False


# ---------------------------------------------------------------------------
# _domain_is_legitimate
# ---------------------------------------------------------------------------


class TestDomainIsLegitimate:
    def test_exact_match(self):
        assert _domain_is_legitimate("edf.fr", ["edf.fr", "edf.com"]) is True

    def test_subdomain_match(self):
        assert _domain_is_legitimate("mail.edf.fr", ["edf.fr"]) is True

    def test_no_match(self):
        assert _domain_is_legitimate("espacionewen.cl", ["edf.fr", "edf.com"]) is False

    def test_similar_but_different(self):
        """edf-secure.com should NOT match edf.com."""
        assert _domain_is_legitimate("edf-secure.com", ["edf.fr", "edf.com"]) is False


# ---------------------------------------------------------------------------
# BrandCheckResult.to_prompt_text
# ---------------------------------------------------------------------------


class TestBrandCheckResultPrompt:
    def test_no_impersonation(self):
        result = BrandCheckResult()
        assert result.to_prompt_text() == ""

    def test_impersonation_text(self):
        result = BrandCheckResult(
            is_impersonation=True,
            claimed_brand="edf",
            expected_domains=["edf.fr", "edf.com"],
            actual_domain="espacionewen.cl",
        )
        text = result.to_prompt_text()
        assert "USURPATION" in text
        assert "edf" in text
        assert "espacionewen.cl" in text
        assert "edf.fr" in text


# ---------------------------------------------------------------------------
# Fake domain in local part detection
# ---------------------------------------------------------------------------


class TestFakeDomainInLocalPart:
    def test_bauhaus_fake_domain(self):
        """Bauhaus-Marktforschung.de@namolixos.info should be detected."""
        result = check_brand_impersonation(
            from_name="BAUHAUS Marktforschung",
            from_address="Bauhaus-Marktforschung.de@namolixos.info",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "bauhaus"
        assert result.actual_domain == "namolixos.info"

    def test_paypal_fake_domain(self):
        """Paypal-auszahlungsabteilung.com@ewartista.org detected via display name."""
        result = check_brand_impersonation(
            from_name="PayPal | Auszahlungs-Abteilung",
            from_address="Paypal-auszahlungsabteilung.com@ewartista.org",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "paypal"

    def test_generic_fake_domain(self):
        """Unknown brand but fake domain pattern still flagged."""
        result = check_brand_impersonation(
            from_name="Some Company",
            from_address="some-company.com@attacker.org",
        )
        assert result.is_impersonation is True
        assert result.actual_domain == "attacker.org"

    def test_normal_email_not_flagged(self):
        """Normal email addresses should not trigger fake domain detection."""
        result = check_brand_impersonation(
            from_name="John Doe",
            from_address="john.doe@company.com",
        )
        assert result.is_impersonation is False

    def test_legitimate_email_with_dots_not_flagged(self):
        """Emails like first.last@company.com should not be flagged."""
        result = check_brand_impersonation(
            from_name="Service Client",
            from_address="service.client@edf.fr",
        )
        assert result.is_impersonation is False


# ---------------------------------------------------------------------------
# German/European brand detection
# ---------------------------------------------------------------------------


class TestGermanBrands:
    def test_bauhaus_impersonation(self):
        result = check_brand_impersonation(
            from_name="BAUHAUS",
            from_address="info@fake-bauhaus.xyz",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "bauhaus"

    def test_bauhaus_legitimate(self):
        result = check_brand_impersonation(
            from_name="BAUHAUS",
            from_address="newsletter@bauhaus.info",
        )
        assert result.is_impersonation is False

    def test_telekom_impersonation(self):
        result = check_brand_impersonation(
            from_name="Deutsche Telekom",
            from_address="service@telekom-sicherheit.net",
        )
        assert result.is_impersonation is True
        assert result.claimed_brand == "telekom"

    def test_sparkasse_impersonation(self):
        result = check_brand_impersonation(
            from_name="Sparkasse Online",
            from_address="sicherheit@sparkasse-verify.com",
        )
        assert result.is_impersonation is True


# ---------------------------------------------------------------------------
# Brand+suffix domain matching (fnacspectacles.com for "fnac")
# ---------------------------------------------------------------------------


class TestBrandVariantDomains:
    """Known brand domain variants listed explicitly in BRAND_DATABASE."""

    def test_fnacspectacles_legitimate(self):
        """fnacspectacles.com is listed as legitimate variant for brand 'fnac'."""
        result = check_brand_impersonation(
            from_name="Fnac Spectacles",
            from_address="noreply@fnacspectacles.com",
        )
        assert result.is_impersonation is False

    def test_fnac_legitimate_exact(self):
        result = check_brand_impersonation(
            from_name="Fnac",
            from_address="noreply@fnac.com",
        )
        assert result.is_impersonation is False

    def test_fnac_impersonation_unrelated(self):
        """A completely unrelated domain should still be flagged."""
        result = check_brand_impersonation(
            from_name="Fnac",
            from_address="noreply@random-shop.xyz",
        )
        assert result.is_impersonation is True

    def test_paypal_phishing_domain_not_accepted(self):
        """paypal-verify.xyz should NOT be accepted — it's phishing, not a brand variant."""
        result = check_brand_impersonation(
            from_name="PayPal",
            from_address="security@paypal-verify.xyz",
        )
        assert result.is_impersonation is True

    def test_edf_phishing_domain_not_accepted(self):
        """edf-secure.com should NOT be accepted — phishing domain."""
        result = check_brand_impersonation(
            from_name="EDF",
            from_address="alerte@edf-secure.com",
        )
        assert result.is_impersonation is True

    def test_fnacdarty_legitimate(self):
        """fnacdarty.com is listed as legitimate for both fnac and darty."""
        result = check_brand_impersonation(
            from_name="Fnac Darty",
            from_address="noreply@fnacdarty.com",
        )
        assert result.is_impersonation is False


# ---------------------------------------------------------------------------
# La Poste notification domain
# ---------------------------------------------------------------------------


class TestLaPosteNotificationDomain:
    def test_notif_colissimo_laposte_legitimate(self):
        """notif-colissimo-laposte.info is a legitimate La Poste sending domain."""
        result = check_brand_impersonation(
            from_name="La Poste - Colissimo",
            from_address="noreply@notif-colissimo-laposte.info",
        )
        assert result.is_impersonation is False

    def test_colissimo_notif_domain_legitimate(self):
        """Same domain for brand 'colissimo'."""
        result = check_brand_impersonation(
            from_name="Colissimo",
            from_address="suivi@notif-colissimo-laposte.info",
        )
        assert result.is_impersonation is False

    def test_laposte_subdomain_notif(self):
        """Subdomain of notif-colissimo-laposte.info also legitimate."""
        result = check_brand_impersonation(
            from_name="La Poste",
            from_address="noreply@mail.notif-colissimo-laposte.info",
        )
        assert result.is_impersonation is False
