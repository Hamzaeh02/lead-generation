"""ICPScore: how well a company (+ its contacts) matches a saved ICPProfile.

Every criterion is independently optional on the profile — an unset one
simply contributes nothing, positive or negative. Weights are configurable
per-profile (ICPProfile.weights overrides DEFAULT_WEIGHTS) so a workspace
can emphasize industry over location, etc. `matched_criteria` explains the
score in plain terms, following the platform's "never a black box" rule
for scoring (section 83, source-comparison transparency).
"""
from __future__ import annotations

from app.models.company import Company
from app.models.contact import Contact
from app.models.icp_profile import ICPProfile

DEFAULT_WEIGHTS: dict[str, int] = {
    "industry": 30,
    "location": 25,
    "company_size": 20,
    "decision_maker": 15,
    "keywords": 10,
}


def _weight(icp: ICPProfile, key: str) -> int:
    return int(icp.weights.get(key, DEFAULT_WEIGHTS[key]))


def _industry_score(company: Company, icp: ICPProfile) -> tuple[float, str | None]:
    if not icp.industry or not company.industry:
        return 0.0, None
    target = icp.industry.strip().lower()
    actual = company.industry.strip().lower()
    if target == actual or target in actual or actual in target:
        return float(_weight(icp, "industry")), f"industry matches '{icp.industry}'"
    return 0.0, None


def _location_score(company: Company, icp: ICPProfile) -> tuple[float, str | None]:
    fields = [
        (icp.city, company.city, "city"),
        (icp.state, company.state, "state"),
        (icp.country, company.country, "country"),
    ]
    set_fields = [(target, actual, label) for target, actual, label in fields if target]
    if not set_fields:
        return 0.0, None

    matched_labels = [
        label
        for target, actual, label in set_fields
        if actual and target.strip().lower() == actual.strip().lower()
    ]
    if not matched_labels:
        return 0.0, None

    fraction = len(matched_labels) / len(set_fields)
    return _weight(icp, "location") * fraction, f"location matches on {', '.join(matched_labels)}"


def _company_size_score(company: Company, icp: ICPProfile) -> tuple[float, str | None]:
    if icp.employee_count_min is None and icp.employee_count_max is None:
        return 0.0, None
    if company.employee_count is None:
        return 0.0, None
    lo = icp.employee_count_min if icp.employee_count_min is not None else 0
    hi = icp.employee_count_max if icp.employee_count_max is not None else float("inf")
    if lo <= company.employee_count <= hi:
        return float(_weight(icp, "company_size")), f"company size {company.employee_count} in target range"
    return 0.0, None


def _decision_maker_score(contacts: list[Contact], icp: ICPProfile) -> tuple[float, str | None]:
    if not icp.target_titles:
        return 0.0, None
    targets = [t.strip().lower() for t in icp.target_titles]
    for contact in contacts:
        if not contact.job_title:
            continue
        title = contact.job_title.strip().lower()
        if any(t == title or t in title for t in targets):
            return float(_weight(icp, "decision_maker")), f"decision-maker contact found ({contact.job_title})"
    return 0.0, None


def _keyword_score(company: Company, icp: ICPProfile) -> tuple[float, str | None]:
    if not icp.keywords:
        return 0.0, None
    haystack = " ".join(filter(None, [company.name, company.description])).lower()
    if not haystack:
        return 0.0, None
    matched = [kw for kw in icp.keywords if kw.strip().lower() in haystack]
    if matched:
        return float(_weight(icp, "keywords")), f"keywords matched: {', '.join(matched)}"
    return 0.0, None


def compute_icp_score(
    company: Company, contacts: list[Contact], icp: ICPProfile
) -> tuple[int, list[str]]:
    total = 0.0
    matched_criteria: list[str] = []

    for scorer, args in (
        (_industry_score, (company, icp)),
        (_location_score, (company, icp)),
        (_company_size_score, (company, icp)),
        (_decision_maker_score, (contacts, icp)),
        (_keyword_score, (company, icp)),
    ):
        points, description = scorer(*args)
        total += points
        if description:
            matched_criteria.append(description)

    return min(round(total), 100), matched_criteria
