from app.services.normalization import (
    extract_domain_from_email,
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_url,
)


def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  John.Doe@Example.COM ") == "john.doe@example.com"


def test_normalize_email_none():
    assert normalize_email(None) is None
    assert normalize_email("") is None


def test_extract_domain_from_email():
    assert extract_domain_from_email("jane@Acme.com") == "acme.com"
    assert extract_domain_from_email("not-an-email") is None
    assert extract_domain_from_email(None) is None


def test_normalize_domain_from_bare_domain():
    assert normalize_domain("WWW.Example.com") == "example.com"


def test_normalize_domain_from_url():
    assert normalize_domain("https://www.example.com/path?x=1") == "example.com"


def test_normalize_domain_from_email():
    assert normalize_domain("person@sub.example.com") == "sub.example.com"


def test_normalize_domain_none():
    assert normalize_domain(None) is None


def test_normalize_url_strips_tracking_params_and_trailing_slash():
    # Only known tracking-param prefixes are stripped (utm_, gclid, ref_, ...) —
    # an unprefixed "ref" is left alone since it may carry real meaning.
    result = normalize_url("https://Example.com/Path/?utm_source=x&ref=1&keep=2")
    assert result == "https://example.com/Path?ref=1&keep=2"


def test_normalize_url_none():
    assert normalize_url(None) is None


def test_normalize_company_name_strips_legal_suffix_and_punctuation():
    assert normalize_company_name("Acme, Inc.") == "acme"
    assert normalize_company_name("Sunshine Roofing Co") == "sunshine roofing"


def test_normalize_company_name_none():
    assert normalize_company_name(None) is None


def test_normalize_phone_preserves_plus_prefix():
    assert normalize_phone("+1 (555) 010-0001") == "+15550100001"


def test_normalize_phone_without_plus():
    assert normalize_phone("555-010-0001") == "5550100001"


def test_normalize_phone_none():
    assert normalize_phone(None) is None
    assert normalize_phone("abc") is None
