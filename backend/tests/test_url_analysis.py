"""Tests for URL analysis service (phishing/spam detection) — pure functions."""

import base64

from app.services.url_analysis import (
    ExtractedUrl,
    _are_related_domains,
    _check_affiliate_params,
    _check_base64_urls,
    _check_deceptive_subdomain,
    _check_email_in_url,
    _check_gibberish_domain,
    _check_gibberish_path,
    _check_s3_bucket_hosting,
    _check_sender_domain_mismatch,
    _find_homoglyphs,
    _is_redirect_script,
    _is_tracking_redirect,
    _shannon_entropy,
    analyze_email_urls,
    analyze_urls,
    extract_urls_from_html,
)

# ---------------------------------------------------------------------------
# extract_urls_from_html
# ---------------------------------------------------------------------------


class TestExtractUrlsFromHtml:
    def test_basic_link(self):
        html = '<a href="https://example.com">Click here</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0].href == "https://example.com"
        assert urls[0].display_text == "Click here"
        assert urls[0].domain == "example.com"

    def test_multiple_links(self):
        html = """
        <a href="https://a.com">A</a>
        <a href="https://b.com">B</a>
        <a href="https://c.com">C</a>
        """
        urls = extract_urls_from_html(html)
        assert len(urls) == 3

    def test_skips_mailto(self):
        html = '<a href="mailto:test@example.com">Email</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 0

    def test_skips_tel(self):
        html = '<a href="tel:+33123456789">Call</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 0

    def test_empty_html(self):
        assert extract_urls_from_html("") == []
        assert extract_urls_from_html(None) == []

    def test_no_links(self):
        html = "<p>Hello world</p>"
        urls = extract_urls_from_html(html)
        assert len(urls) == 0


# ---------------------------------------------------------------------------
# _find_homoglyphs
# ---------------------------------------------------------------------------


class TestFindHomoglyphs:
    def test_clean_domain(self):
        assert _find_homoglyphs("paypal.com") == []

    def test_cyrillic_a(self):
        # Replace 'a' with Cyrillic а (U+0430)
        domain = "p\u0430ypal.com"
        found = _find_homoglyphs(domain)
        assert len(found) == 1
        assert "U+0430" in found[0]

    def test_multiple_homoglyphs(self):
        # Cyrillic а and о
        domain = "p\u0430yp\u043el.com"
        found = _find_homoglyphs(domain)
        assert len(found) == 2


# ---------------------------------------------------------------------------
# _check_deceptive_subdomain
# ---------------------------------------------------------------------------


class TestCheckDeceptiveSubdomain:
    def test_legitimate_domain(self):
        assert _check_deceptive_subdomain("www.paypal.com") is None

    def test_deceptive_subdomain(self):
        result = _check_deceptive_subdomain("paypal.com.evil.xyz")
        assert result is not None
        assert "paypal" in result.lower()

    def test_short_domain(self):
        # Only 2 parts — cannot be deceptive
        assert _check_deceptive_subdomain("evil.xyz") is None


# ---------------------------------------------------------------------------
# _is_tracking_redirect
# ---------------------------------------------------------------------------


class TestIsTrackingRedirect:
    def test_mailchimp(self):
        assert _is_tracking_redirect("list-manage.com")

    def test_sendgrid(self):
        assert _is_tracking_redirect("sendgrid.net")

    def test_subdomain_of_tracking(self):
        assert _is_tracking_redirect("click.sendgrid.net")

    def test_tracking_prefix_known_parent(self):
        """click.sendgrid.net is tracking: 'click.' prefix + sendgrid.net in KNOWN_TRACKING_DOMAINS."""
        assert _is_tracking_redirect("click.sendgrid.net")

    def test_tracking_prefix_unknown_parent(self):
        """click.example.com is NOT tracking: 'click.' prefix but example.com not in KNOWN_TRACKING_DOMAINS."""
        assert not _is_tracking_redirect("click.example.com")

    def test_tracking_prefix_hubspot(self):
        """track.hubspot.com is tracking: 'track.' prefix + hubspot.com in KNOWN_TRACKING_DOMAINS."""
        assert _is_tracking_redirect("track.hubspot.com")

    def test_unknown_domain(self):
        assert not _is_tracking_redirect("evil-phishing.xyz")


# ---------------------------------------------------------------------------
# _check_gibberish_domain
# ---------------------------------------------------------------------------


class TestCheckGibberishDomain:
    def test_normal_domain(self):
        assert _check_gibberish_domain("google.com") is None

    def test_gibberish_domain(self):
        # Short, mixed digits+letters, high entropy
        result = _check_gibberish_domain("dfhv4y.com")
        assert result is not None
        assert "suspect" in result.lower()

    def test_tracking_domain_skipped(self):
        assert _check_gibberish_domain("click.sendgrid.net") is None

    def test_long_domain_skipped(self):
        # Long domains are not flagged
        assert _check_gibberish_domain("thisisaverylongdomainname.com") is None


# ---------------------------------------------------------------------------
# _shannon_entropy
# ---------------------------------------------------------------------------


class TestShannonEntropy:
    def test_empty(self):
        assert _shannon_entropy("") == 0.0

    def test_single_char(self):
        assert _shannon_entropy("aaaa") == 0.0

    def test_random_string_higher(self):
        # Random-looking string should have higher entropy
        e_random = _shannon_entropy("dfhv4y")
        e_word = _shannon_entropy("hello")
        assert e_random > e_word


# ---------------------------------------------------------------------------
# _check_base64_urls
# ---------------------------------------------------------------------------


class TestCheckBase64Urls:
    def test_clean_url(self):
        assert _check_base64_urls("https://example.com/page?ref=123") == []

    def test_base64_encoded_url(self):
        encoded = base64.b64encode(b"https://evil.com/phish").decode()
        result = _check_base64_urls(f"https://tracker.com/click?u={encoded}")
        assert len(result) > 0
        assert "base64" in result[0].lower()

    def test_short_param_ignored(self):
        # Too short to be a meaningful base64 URL
        assert _check_base64_urls("https://example.com?u=abc") == []


# ---------------------------------------------------------------------------
# _check_email_in_url
# ---------------------------------------------------------------------------


class TestCheckEmailInUrl:
    def test_no_email(self):
        assert _check_email_in_url("https://example.com/page?id=123") == []

    def test_email_in_params(self):
        result = _check_email_in_url("https://tracker.com/click?e=user@real.com")
        assert len(result) == 1
        assert "email" in result[0].lower() or "adresse" in result[0].lower()

    def test_example_email_ignored(self):
        result = _check_email_in_url("https://docs.com/page?e=test@example.com")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# _is_redirect_script
# ---------------------------------------------------------------------------


class TestIsRedirectScript:
    def test_click_php(self):
        assert _is_redirect_script("https://evil.com/click.php?url=http://target.com")

    def test_redirect_php(self):
        assert _is_redirect_script("https://evil.com/redirect.php?u=abc")

    def test_normal_url(self):
        assert not _is_redirect_script("https://example.com/about")

    def test_known_tracking_not_flagged(self):
        assert not _is_redirect_script("https://click.sendgrid.net/click?id=123")


# ---------------------------------------------------------------------------
# _check_affiliate_params
# ---------------------------------------------------------------------------


class TestCheckAffiliateParams:
    def test_no_affiliate_params(self):
        assert _check_affiliate_params("https://example.com/page") is None

    def test_single_param_not_flagged(self):
        # Need >=2 to flag
        assert _check_affiliate_params("https://example.com?aff_id=123") is None

    def test_multiple_affiliate_params(self):
        result = _check_affiliate_params("https://scam.com?aff_id=123&offer_id=456&sub_id=789")
        assert result is not None
        assert "affiliation" in result.lower()


# ---------------------------------------------------------------------------
# analyze_urls — integration of all checks
# ---------------------------------------------------------------------------


class TestAnalyzeUrls:
    def test_clean_urls(self):
        urls = [
            ExtractedUrl(href="https://example.com", display_text="Example", domain="example.com")
        ]
        result = analyze_urls(urls)
        assert not result.has_suspicious
        assert result.total_urls == 1

    def test_shortener_detected(self):
        urls = [ExtractedUrl(href="https://bit.ly/abc123", display_text="Click", domain="bit.ly")]
        result = analyze_urls(urls)
        assert result.has_suspicious
        assert any(
            "raccourcisseur" in r.lower() for s in result.suspicious_urls for r in s["reasons"]
        )

    def test_ip_address_detected(self):
        """Public IP addresses should be flagged as suspicious."""
        urls = [
            ExtractedUrl(
                href="http://185.23.45.67/login", display_text="Login", domain="185.23.45.67"
            )
        ]
        result = analyze_urls(urls)
        assert result.has_suspicious
        assert any("IP" in r for s in result.suspicious_urls for r in s["reasons"])

    def test_display_mismatch_detected(self):
        urls = [
            ExtractedUrl(
                href="https://evil.com/login",
                display_text="paypal.com",
                domain="evil.com",
            )
        ]
        result = analyze_urls(urls)
        assert result.has_suspicious
        assert any("trompeur" in r.lower() for s in result.suspicious_urls for r in s["reasons"])

    def test_display_mismatch_tracking_not_flagged(self):
        urls = [
            ExtractedUrl(
                href="https://click.sendgrid.net/redirect?url=...",
                display_text="mysite.com",
                domain="click.sendgrid.net",
            )
        ]
        result = analyze_urls(urls)
        # Tracking redirects should NOT be flagged for display mismatch
        mismatches = [
            r for s in result.suspicious_urls for r in s["reasons"] if "trompeur" in r.lower()
        ]
        assert len(mismatches) == 0


# ---------------------------------------------------------------------------
# analyze_email_urls — full pipeline
# ---------------------------------------------------------------------------


class TestAnalyzeEmailUrls:
    def test_none_html(self):
        result = analyze_email_urls(None)
        assert result.total_urls == 0
        assert not result.has_suspicious

    def test_html_with_clean_link(self):
        html = '<a href="https://example.com">Visit</a>'
        result = analyze_email_urls(html)
        assert result.total_urls == 1
        assert not result.has_suspicious

    def test_html_with_suspicious_link(self):
        html = '<a href="https://bit.ly/scam">Click here</a>'
        result = analyze_email_urls(html)
        assert result.has_suspicious

    def test_prompt_text_clean(self):
        result = analyze_email_urls('<a href="https://example.com">OK</a>')
        text = result.to_prompt_text()
        assert "Aucune URL suspecte" in text

    def test_prompt_text_suspicious(self):
        result = analyze_email_urls('<a href="https://bit.ly/x">Click</a>')
        text = result.to_prompt_text()
        assert "SUSPECTE" in text


# ---------------------------------------------------------------------------
# _check_s3_bucket_hosting
# ---------------------------------------------------------------------------


class TestCheckS3BucketHosting:
    def test_s3_regional_bucket(self):
        """Detect S3 bucket with regional endpoint (common phishing pattern)."""
        result = _check_s3_bucket_hosting(
            "managed-marketplace-endpoint-a8.s3.us-west-1.amazonaws.com",
            "https://managed-marketplace-endpoint-a8.s3.us-west-1.amazonaws.com/7BK2nxC46",
        )
        assert result is not None
        assert "S3" in result

    def test_s3_global_bucket(self):
        result = _check_s3_bucket_hosting(
            "mybucket.s3.amazonaws.com",
            "https://mybucket.s3.amazonaws.com/page.html",
        )
        assert result is not None
        assert "S3" in result

    def test_s3_path_style(self):
        result = _check_s3_bucket_hosting(
            "s3.us-west-2.amazonaws.com",
            "https://s3.us-west-2.amazonaws.com/bucket/file",
        )
        assert result is not None

    def test_non_s3_amazonaws(self):
        """awstrack.me (SES tracking) should NOT be flagged as S3."""
        result = _check_s3_bucket_hosting(
            "awstrack.me",
            "https://awstrack.me/click/123",
        )
        assert result is None

    def test_normal_domain(self):
        result = _check_s3_bucket_hosting(
            "example.com",
            "https://example.com/page",
        )
        assert result is None


# ---------------------------------------------------------------------------
# _check_sender_domain_mismatch (re-enabled)
# ---------------------------------------------------------------------------


class TestCheckSenderDomainMismatch:
    def test_matching_domains(self):
        """Same domain → no mismatch."""
        result = _check_sender_domain_mismatch("edf.fr", "edf.fr")
        assert result is None

    def test_subdomain_of_sender(self):
        """Subdomain of sender → no mismatch."""
        result = _check_sender_domain_mismatch("mail.edf.fr", "edf.fr")
        assert result is None

    def test_tracking_service_not_flagged(self):
        """Known tracking services should not be flagged."""
        result = _check_sender_domain_mismatch("click.sendgrid.net", "edf.fr")
        assert result is None

    def test_unrelated_domain_flagged(self):
        """Truly unrelated domain should be flagged."""
        result = _check_sender_domain_mismatch("espacionewen.cl", "edf.fr")
        assert result is not None
        assert "expéditeur" in result.lower()

    def test_cdn_domain_not_flagged(self):
        """CDN domains should not be flagged."""
        result = _check_sender_domain_mismatch("cloudfront.net", "edf.fr")
        assert result is None

    def test_social_domain_not_flagged(self):
        """Social media links in emails should not be flagged."""
        result = _check_sender_domain_mismatch("youtube.com", "newsletter.example.com")
        assert result is None


# ---------------------------------------------------------------------------
# _is_redirect_script — /rd/ pattern
# ---------------------------------------------------------------------------


class TestRedirectScriptRdPath:
    def test_rd_path_detected(self):
        """Short /rd/ redirect path should be flagged."""
        assert _is_redirect_script("http://serviice.casacam.net/rd/4lBwjm6146jMFT1083")

    def test_rd_path_with_long_token(self):
        assert _is_redirect_script("http://evil.com/rd/aB3xK9mW2pQ7nL4yH8vJ6tR1")

    def test_normal_path_not_flagged(self):
        assert not _is_redirect_script("https://example.com/about")

    def test_tracking_rd_not_flagged(self):
        """Known tracking services with /rd/ should not be flagged."""
        assert not _is_redirect_script("https://click.sendgrid.net/rd/something")

    def test_sender_own_subdomain_not_flagged(self):
        """Sender's own tracking subdomain should not be flagged."""
        assert not _is_redirect_script(
            "https://mailing.github.com/ls/click?upn=abc123",
            sender_domain="github.com",
        )

    def test_sender_own_links_subdomain_not_flagged(self):
        """HomeExchange links.homeexchange.com should not be flagged."""
        assert not _is_redirect_script(
            "https://links.homeexchange.com/a/click?_t=abc123",
            sender_domain="info.homeexchange.com",
        )


# ---------------------------------------------------------------------------
# _check_gibberish_path
# ---------------------------------------------------------------------------


class TestCheckGibberishPath:
    def test_long_random_path(self):
        """Long mixed-case alphanumeric path = suspicious."""
        result = _check_gibberish_path(
            "http://evil.com/rd/4lBwjm6146jMFT1083jrtdqxitlf1161HEZTUDIWLHJKWCN112784NZBG"
        )
        assert result is not None
        assert "aléatoire" in result.lower()

    def test_normal_path(self):
        """Normal URL paths should not be flagged."""
        assert _check_gibberish_path("https://example.com/about/contact") is None

    def test_short_path(self):
        """Short paths should not be flagged."""
        assert _check_gibberish_path("https://example.com/rd/abc") is None

    def test_uuid_path_not_flagged(self):
        """UUID-like paths (with dashes) should not be flagged."""
        assert (
            _check_gibberish_path("https://example.com/item/f07edfbf-2420-41a4-97c7-4690ac553f4f")
            is None
        )

    def test_base64_path_not_flagged(self):
        """Base64-like paths (with =) should not be flagged."""
        assert (
            _check_gibberish_path("https://example.com/data/dGhpcyBpcyBhIGJhc2U2NCBzdHJpbmc=")
            is None
        )

    def test_sender_own_tracking_not_flagged(self):
        """Sender's own tracking subdomain tokens should not be flagged."""
        assert (
            _check_gibberish_path(
                "https://links.homeexchange.com/s/c/rkjf60EkXWRJfbdRQyWl4djqt1og5VWH",
                sender_domain="info.homeexchange.com",
            )
            is None
        )

    def test_unrelated_domain_still_flagged(self):
        """Unrelated domains with gibberish paths should still be flagged."""
        result = _check_gibberish_path(
            "http://evil.com/rd/4lBwjm6146jMFT1083jrtdqxitlf1161HEZTUDI",
            sender_domain="homeexchange.com",
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Full integration: BAUHAUS phishing email
# ---------------------------------------------------------------------------


class TestBauhausPhishingIntegration:
    def test_bauhaus_phishing_url(self):
        """The BAUHAUS phishing email URL should trigger multiple signals."""
        html = '<a href="http://serviice.casacam.net/rd/4lBwjm6146jMFT1083jrtdqxitlf1161HEZTUDIWLHJKWCN112784NZBG15222W13">Jetzt Umfrage starten</a>'
        result = analyze_email_urls(html, sender_domain="namolixos.info")
        assert result.has_suspicious
        assert len(result.suspicious_urls) > 0
        reasons = result.suspicious_urls[0]["reasons"]
        # Should detect at least: redirect script (/rd/), gibberish path, sender mismatch
        assert len(reasons) >= 2


# ---------------------------------------------------------------------------
# Webmail sender mismatch skipping
# ---------------------------------------------------------------------------


class TestWebmailSenderSkip:
    def test_gmail_sender_not_flagged(self):
        """URLs in emails from gmail.com should not trigger sender mismatch."""
        result = _check_sender_domain_mismatch("www.ryanair.com", "gmail.com")
        assert result is None

    def test_outlook_sender_not_flagged(self):
        result = _check_sender_domain_mismatch("booking.com", "outlook.com")
        assert result is None

    def test_gmx_sender_not_flagged(self):
        result = _check_sender_domain_mismatch("amazon.fr", "gmx.com")
        assert result is None

    def test_protonmail_sender_not_flagged(self):
        result = _check_sender_domain_mismatch("example.com", "protonmail.com")
        assert result is None

    def test_corporate_sender_still_flagged(self):
        """Non-webmail corporate senders should still be checked."""
        result = _check_sender_domain_mismatch("evil-phishing.com", "edf.fr")
        assert result is not None


# ---------------------------------------------------------------------------
# _are_related_domains
# ---------------------------------------------------------------------------


class TestAreRelatedDomains:
    def test_urssaf_net_entreprises(self):
        """URSSAF and net-entreprises are related."""
        assert _are_related_domains("www.net-entreprises.fr", "urssaf.fr")

    def test_urssaf_letese(self):
        """URSSAF and letese are related."""
        assert _are_related_domains("www.letese.urssaf.fr", "urssaf.fr")

    def test_google_youtube(self):
        """Google and YouTube are related."""
        assert _are_related_domains("youtube.com", "google.com")

    def test_unrelated_domains(self):
        """Truly unrelated domains should not match."""
        assert not _are_related_domains("evil.com", "urssaf.fr")

    def test_same_domain(self):
        """Same domain is not 'related' by groups (handled by core comparison)."""
        # Same core → handled elsewhere, not by related groups
        assert not _are_related_domains("edf.fr", "edf.fr")

    def test_laposte_colissimo(self):
        """La Poste and Colissimo are related."""
        assert _are_related_domains("colissimo.fr", "laposte.fr")


# ---------------------------------------------------------------------------
# False positive integration: URSSAF legitimate email
# ---------------------------------------------------------------------------


class TestUrssafLegitimateEmail:
    def test_urssaf_with_net_entreprises_link(self):
        """URSSAF email with net-entreprises.fr link should NOT be suspicious."""
        html = '<a href="https://www.net-entreprises.fr">net-entreprises</a>'
        result = analyze_email_urls(html, sender_domain="urssaf.fr")
        assert not result.has_suspicious

    def test_urssaf_with_letese_link(self):
        """URSSAF email with letese.urssaf.fr link should NOT be suspicious."""
        html = '<a href="https://www.letese.urssaf.fr">le TESE</a>'
        result = analyze_email_urls(html, sender_domain="urssaf.fr")
        assert not result.has_suspicious


# ---------------------------------------------------------------------------
# False positive integration: forwarded email from gmail
# ---------------------------------------------------------------------------


class TestForwardedEmailFromWebmail:
    def test_gmail_forward_with_ryanair_link(self):
        """Forwarded email from gmail with ryanair link should NOT be suspicious."""
        html = '<a href="https://www.ryanair.com/fr/fr/myryanair/">Mon vol</a>'
        result = analyze_email_urls(html, sender_domain="gmail.com")
        assert not result.has_suspicious

    def test_outlook_forward_with_booking_link(self):
        """Forward from outlook with booking.com should NOT be suspicious."""
        html = '<a href="https://www.booking.com/reservation">Réservation</a>'
        result = analyze_email_urls(html, sender_domain="outlook.com")
        assert not result.has_suspicious


# ---------------------------------------------------------------------------
# Known tracking domains: gibberish path should be skipped
# ---------------------------------------------------------------------------


class TestTrackingDomainGibberishSkip:
    def test_awstrack_me_long_token_not_suspicious(self):
        """awstrack.me URLs have long random tokens — should NOT trigger gibberish path."""
        html = (
            '<a href="https://awstrack.me/aB3cD4eF5gH6iJ7kL8mN9oP0qR1s'
            'T2uV3wX4yZ5aB6cD7eF8gH9i">Cliquez ici</a>'
        )
        result = analyze_email_urls(html, sender_domain="transavia.com")
        assert not result.has_suspicious

    def test_delight_data_not_suspicious(self):
        """delight-data.com is a known tracking platform."""
        html = '<a href="https://delight-data.com/track/campaign/abc123">Voir</a>'
        result = analyze_email_urls(html, sender_domain="theatre-renaissance.fr")
        assert not result.has_suspicious

    def test_pegacloud_not_suspicious(self):
        """pegacloud.io is a known marketing platform."""
        html = '<a href="https://pegacloud.io/em/abc123?utm=campaign">Offre</a>'
        result = analyze_email_urls(html, sender_domain="transavia.com")
        assert not result.has_suspicious


# ---------------------------------------------------------------------------
# Private/loopback IP addresses should not be flagged
# ---------------------------------------------------------------------------


class TestPrivateIPNotFlagged:
    def test_localhost_127_not_suspicious(self):
        """127.0.0.1 in URLs (common in dev/GitHub issues) should not be flagged."""
        html = '<a href="http://127.0.0.1:8080/test">localhost</a>'
        result = analyze_email_urls(html, sender_domain="github.com")
        assert not result.has_suspicious

    def test_private_10_network_not_suspicious(self):
        """10.x.x.x private IPs should not be flagged."""
        html = '<a href="http://10.0.0.1/admin">Internal</a>'
        result = analyze_email_urls(html, sender_domain="github.com")
        assert not result.has_suspicious

    def test_private_192_168_not_suspicious(self):
        """192.168.x.x private IPs should not be flagged."""
        html = '<a href="http://192.168.1.1/config">Router</a>'
        result = analyze_email_urls(html, sender_domain="github.com")
        assert not result.has_suspicious

    def test_public_ip_still_suspicious(self):
        """Public IP addresses (non-private) should still be flagged."""
        html = '<a href="http://185.23.45.67/login">Click</a>'
        result = analyze_email_urls(html, sender_domain="bank.com")
        assert result.has_suspicious


# ---------------------------------------------------------------------------
# Related domain groups (Microsoft, La Poste, GitHub ecosystem)
# ---------------------------------------------------------------------------


class TestRelatedDomainGroups:
    def test_microsoft_accountprotection(self):
        """accountprotection.microsoft.com linked from account.live.com is legitimate."""
        html = '<a href="https://accountprotection.microsoft.com/verify">Vérifier</a>'
        result = analyze_email_urls(html, sender_domain="account.live.com")
        assert not result.has_suspicious

    def test_laposte_notif_colissimo_domain(self):
        """notif-colissimo-laposte.info sending emails with laposte.fr links."""
        html = '<a href="https://www.laposte.fr/suivi-colissimo">Suivi colis</a>'
        result = analyze_email_urls(html, sender_domain="notif-colissimo-laposte.info")
        assert not result.has_suspicious

    def test_github_pytorch_link(self):
        """GitHub notification emails may contain pytorch.org links."""
        html = '<a href="https://pytorch.org/docs/stable/">PyTorch docs</a>'
        result = analyze_email_urls(html, sender_domain="github.com")
        assert not result.has_suspicious
