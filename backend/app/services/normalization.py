"""Pure normalization functions used before dedup/entity resolution.

These never invent data — they only reshape/clean values that are already
present (lowercasing, stripping punctuation, removing tracking params).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

_LEGAL_SUFFIXES = (
    "inc", "incorporated", "llc", "l.l.c", "ltd", "limited", "corp", "corporation",
    "co", "company", "plc", "gmbh", "srl", "sa", "bv", "pty", "llp",
)
_TRACKING_PARAM_PREFIXES = ("utm_", "gclid", "fbclid", "msclkid", "mc_", "ref_")


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    cleaned = email.strip().lower()
    return cleaned or None


def extract_domain_from_email(email: str | None) -> str | None:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        return None
    return normalized.rsplit("@", 1)[-1] or None


def normalize_domain(value: str | None) -> str | None:
    """Accepts a bare domain, an email, or a full URL and returns a bare
    lowercase host with no scheme, path, port, or leading `www.`."""
    if not value:
        return None
    value = value.strip()
    if "@" in value and "://" not in value:
        value = extract_domain_from_email(value) or value

    if "://" not in value:
        value = f"https://{value}"

    host = urlparse(value).netloc.lower()
    host = host.split("@")[-1]  # strip userinfo if present
    host = host.split(":")[0]  # strip port
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_url(value: str | None) -> str | None:
    """Lowercases the host, strips known tracking query params, and drops a
    trailing slash on bare-path URLs. Preserves the rest of the URL as-is —
    this is cleanup, not a rewrite of what the source actually returned."""
    if not value:
        return None
    value = value.strip()
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    host = parsed.netloc.lower()

    query_pairs = [
        pair for pair in parsed.query.split("&") if pair and not _is_tracking_param(pair)
    ]
    query = "&".join(query_pairs)

    path = parsed.path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    return urlunparse((parsed.scheme or "https", host, path, "", query, ""))


def _is_tracking_param(pair: str) -> bool:
    key = pair.split("=", 1)[0].lower()
    return any(key.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def normalize_company_name(name: str | None) -> str | None:
    """Lowercases, strips punctuation, and removes common legal suffixes so
    'Acme Inc.' and 'ACME, Inc' compare equal. The original `name` field is
    always preserved separately — this is only for matching."""
    if not name:
        return None
    lowered = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in lowered.split() if t]
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    normalized = " ".join(tokens).strip()
    return normalized or None


def normalize_phone(phone: str | None) -> str | None:
    """Best-effort normalization to a leading-`+` digit string. This is not
    a full E.164 implementation (no libphonenumber dependency) — it only
    strips formatting characters and preserves whatever digits/country
    prefix the source actually provided."""
    if not phone:
        return None
    has_plus = phone.strip().startswith("+")
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    return f"+{digits}" if has_plus else digits
