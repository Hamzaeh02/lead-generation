"""Rule-based (regex/keyword) natural-language ICP parser.

This is deliberately NOT an AI/LLM parser — no OpenAI-compatible AIProvider
integration exists yet (that's Phase 10). Building a fake "AI interpretation"
without a real model would be worse than being upfront: this does plain
keyword/regex extraction and is honestly limited compared to what an LLM
parser will do later. Per section 31's own requirement, the output is
always a suggestion for the user to review/edit — never executed or saved
automatically — so a heuristic parser is a legitimate placeholder rather
than a shortcut around that rule. Swap this out for a real AIProvider-backed
parser in Phase 10 without changing the API contract (NLICPParseResponse).
"""
from __future__ import annotations

import re

from app.schemas.icp_profile import ICPProfileBase, NLICPParseResponse

_INDUSTRY_KEYWORDS = [
    "dental", "dentist", "roofing", "roofer", "plumbing", "plumber",
    "electrician", "restaurant", "cafe", "hotel", "hospitality", "gym",
    "fitness", "software", "saas", "agency", "marketing agency", "law firm",
    "legal", "construction", "consulting", "real estate", "insurance",
    "manufacturing", "retail", "logistics", "healthcare", "clinic",
    "financial services", "e-commerce", "ecommerce", "education",
    "hardware store", "bakery", "salon", "auto repair",
]

_US_STATES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

_TARGET_TITLES = [
    "founder", "co-founder", "ceo", "owner", "managing director", "president",
    "marketing director", "head of marketing", "sales director", "head of sales",
    "operations director", "cto", "cfo", "cmo",
]


def _extract_industry(text: str) -> str | None:
    lowered = text.lower()
    for keyword in _INDUSTRY_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def _extract_state(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()
    for name, abbrev in _US_STATES.items():
        if name in lowered:
            return name.title(), "US"
        if re.search(rf"\b{abbrev}\b", text):
            return abbrev, "US"
    return None, None


def _extract_city(text: str, state_name: str | None) -> str | None:
    # "in <City>, <State>" or "in <City> <State>" — best-effort, not a full
    # geocoder. Only fires when a recognized state was also found nearby.
    if not state_name:
        return None
    match = re.search(r"\bin\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\s*,?\s*" + re.escape(state_name), text)
    if match:
        return match.group(1)
    return None


def _extract_employee_range(text: str) -> tuple[int | None, int | None]:
    range_match = re.search(r"(\d+)\s*(?:to|-|–)\s*(\d+)\s*employees", text, re.IGNORECASE)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    under_match = re.search(r"(?:under|fewer than|less than)\s*(\d+)\s*employees", text, re.IGNORECASE)
    if under_match:
        return None, int(under_match.group(1))

    over_match = re.search(r"(?:over|more than)\s*(\d+)\s*employees", text, re.IGNORECASE)
    if over_match:
        return int(over_match.group(1)), None

    plus_match = re.search(r"(\d+)\+\s*employees", text, re.IGNORECASE)
    if plus_match:
        return int(plus_match.group(1)), None

    return None, None


def _extract_titles(text: str) -> list[str]:
    lowered = text.lower()
    return [title for title in _TARGET_TITLES if title in lowered]


def parse_nl_icp(text: str) -> NLICPParseResponse:
    industry = _extract_industry(text)
    state, country = _extract_state(text)
    city = _extract_city(text, state)
    employee_min, employee_max = _extract_employee_range(text)
    titles = _extract_titles(text)

    hints: list[str] = []
    if industry is None:
        hints.append("No recognized industry keyword found — set 'industry' manually if needed.")
    if state is None:
        hints.append("No recognized US state found — set location fields manually if needed.")
    if employee_min is None and employee_max is None:
        hints.append("No employee-count range detected.")
    if not titles:
        hints.append("No recognized decision-maker title found.")

    suggested = ICPProfileBase(
        name="Parsed from natural language",
        industry=industry,
        country=country,
        state=state,
        city=city,
        employee_count_min=employee_min,
        employee_count_max=employee_max,
        target_titles=[t.title() for t in titles],
        keywords=[],
    )
    return NLICPParseResponse(suggested=suggested, unparsed_hints=hints)
