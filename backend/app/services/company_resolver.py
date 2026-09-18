"""CompanyEntityResolver: dedup + provenance for incoming company records.

A candidate NormalizedCompany may describe a company already in the
workspace (seen via a different provider, CSV row, or earlier search).
This resolver decides whether to attach the new evidence to an existing
Company or create a new one — using only strong signals (exact domain,
exact phone, or exact normalized-name+location match). It deliberately
does NOT do fuzzy name-only matching, since that risks silently merging
two different businesses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models.company import Company
from app.providers.base import NormalizedCompany
from app.repositories.company_repository import CompanyRepository
from app.services.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_phone,
    normalize_url,
)

_COMPANY_FIELDS = (
    "name", "website", "phone", "address", "city", "state", "country",
    "postal_code", "industry", "category", "employee_count", "description",
    "linkedin_url",
)


class MatchConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CompanyResolution:
    company: Company
    created: bool
    matched_fields: list[str]
    confidence: MatchConfidence


class CompanyEntityResolver:
    def __init__(self, repo: CompanyRepository) -> None:
        self.repo = repo

    async def resolve(
        self, *, workspace_id: uuid.UUID, candidate: NormalizedCompany
    ) -> CompanyResolution:
        domain = normalize_domain(candidate.domain or candidate.website)
        normalized_name = normalize_company_name(candidate.name)
        phone = normalize_phone(candidate.phone)

        existing, matched_fields, confidence = await self._find_match(
            workspace_id=workspace_id,
            domain=domain,
            normalized_name=normalized_name,
            city=candidate.city,
            state=candidate.state,
            phone=phone,
        )

        provider = candidate.metadata.provider
        retrieved_at = candidate.metadata.retrieved_at.isoformat()

        if existing is not None:
            self._fill_missing_fields(existing, candidate, provider, retrieved_at)
            self.repo.add_source(
                company=existing,
                provider=provider,
                external_id=candidate.metadata.external_id,
                source_url=candidate.metadata.source_url,
                source_type=candidate.metadata.source_type,
                raw_reference=candidate.metadata.raw_reference,
            )
            return CompanyResolution(existing, False, matched_fields, confidence)

        company = await self.repo.create(
            workspace_id=workspace_id,
            name=candidate.name,
            normalized_name=normalized_name,
            domain=domain,
            website=normalize_url(candidate.website),
            phone=phone,
            address=candidate.address,
            city=candidate.city,
            state=candidate.state,
            country=candidate.country,
            postal_code=candidate.postal_code,
            industry=candidate.industry,
            category=candidate.category,
            employee_count=candidate.employee_count,
            description=candidate.description,
            linkedin_url=candidate.linkedin_url,
            social_urls=dict(candidate.social_urls),
            field_provenance=self._provenance_for_set_fields(candidate, provider, retrieved_at),
        )
        self.repo.add_source(
            company=company,
            provider=provider,
            external_id=candidate.metadata.external_id,
            source_url=candidate.metadata.source_url,
            source_type=candidate.metadata.source_type,
            raw_reference=candidate.metadata.raw_reference,
        )
        return CompanyResolution(company, True, [], MatchConfidence.NONE)

    async def _find_match(
        self,
        *,
        workspace_id: uuid.UUID,
        domain: str | None,
        normalized_name: str | None,
        city: str | None,
        state: str | None,
        phone: str | None,
    ) -> tuple[Company | None, list[str], MatchConfidence]:
        if domain:
            match = await self.repo.find_by_domain(workspace_id, domain)
            if match is not None:
                return match, ["domain"], MatchConfidence.HIGH

        if phone:
            match = await self.repo.find_by_phone(workspace_id, phone)
            if match is not None:
                return match, ["phone"], MatchConfidence.HIGH

        if normalized_name and (city or state):
            match = await self.repo.find_by_normalized_name_and_location(
                workspace_id, normalized_name, city, state
            )
            if match is not None:
                matched = ["normalized_name"] + (["city"] if city else []) + (
                    ["state"] if state else []
                )
                return match, matched, MatchConfidence.MEDIUM

        return None, [], MatchConfidence.NONE

    def _fill_missing_fields(
        self, company: Company, candidate: NormalizedCompany, provider: str, retrieved_at: str
    ) -> None:
        """Only fills currently-null fields — never silently overwrites an
        existing value with a new source's data (that requires an explicit
        merge decision, not an automatic one)."""
        provenance = dict(company.field_provenance)
        for field_name in _COMPANY_FIELDS:
            current = getattr(company, field_name)
            incoming = getattr(candidate, field_name, None)
            if current is None and incoming is not None:
                setattr(company, field_name, incoming)
                provenance[field_name] = {"provider": provider, "retrieved_at": retrieved_at}
        if not company.social_urls and candidate.social_urls:
            company.social_urls = dict(candidate.social_urls)
        company.field_provenance = provenance

    def _provenance_for_set_fields(
        self, candidate: NormalizedCompany, provider: str, retrieved_at: str
    ) -> dict[str, Any]:
        provenance: dict[str, Any] = {}
        for field_name in _COMPANY_FIELDS:
            if getattr(candidate, field_name, None) is not None:
                provenance[field_name] = {"provider": provider, "retrieved_at": retrieved_at}
        return provenance
