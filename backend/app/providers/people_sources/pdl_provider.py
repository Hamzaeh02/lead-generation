"""People Data Labs person search (person discovery / decision-maker lookup).

Same caveat as `lead_sources/pdl_provider.py`: built from documented PDL API
conventions, not verified against a live account. Verify field mappings
once a real PDL_API_KEY is in use.

Requires PDL_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedContact,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.http import request_json
from app.providers.people_sources.base import PersonDiscoveryProvider

_BASE_URL = "https://api.peopledatalabs.com"


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


class PeopleDataLabsPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "people_data_labs"
    category = ProviderCategory.PERSON_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("people_data_labs: PDL_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        clauses: list[str] = []
        if criteria.domain:
            clauses.append(f"job_company_website='{_sql_quote(criteria.domain)}'")
        if criteria.job_titles:
            title_clause = " OR ".join(
                f"job_title='{_sql_quote(t)}'" for t in criteria.job_titles
            )
            clauses.append(f"({title_clause})")
        if criteria.country:
            clauses.append(f"location_country='{_sql_quote(criteria.country)}'")
        if criteria.state:
            clauses.append(f"location_region='{_sql_quote(criteria.state)}'")
        if criteria.industry:
            clauses.append(f"job_company_industry='{_sql_quote(criteria.industry)}'")

        return await self._search(clauses, criteria.limit)

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        clauses = [f"job_company_website='{_sql_quote(company_domain)}'"]
        if target_titles:
            title_clause = " OR ".join(
                f"job_title='{_sql_quote(t)}'" for t in target_titles
            )
            clauses.append(f"({title_clause})")
        return await self._search(clauses, limit=25)

    async def _search(self, clauses: list[str], limit: int) -> list[NormalizedContact]:
        sql = "SELECT * FROM person"
        if clauses:
            sql += f" WHERE {' AND '.join(clauses)}"
        payload = await request_json(
            self._client,
            "POST",
            "/v5/person/search",
            provider=self.name,
            headers={"X-Api-Key": self._api_key},
            json={"sql": sql, "size": limit},
        )
        rows = payload.get("data") or []
        return [self._to_contact(row) for row in rows[:limit]]

    def _to_contact(self, row: dict) -> NormalizedContact:
        # PDL returns a bare `true`/`false` in place of the real array for
        # fields gated behind data permissions the API key doesn't have —
        # not just an empty list, so this must be checked before indexing.
        emails = row.get("emails")
        primary_email = (
            emails[0].get("address")
            if isinstance(emails, list) and emails and isinstance(emails[0], dict)
            else None
        )
        phones = row.get("phone_numbers")
        primary_phone = (
            phones[0] if isinstance(phones, list) and phones and isinstance(phones[0], str) else None
        )

        return NormalizedContact(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=row.get("id"),
                source_url=row.get("linkedin_url"),
                source_type="api",
                raw_reference=row,
            ),
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            full_name=row.get("full_name"),
            job_title=row.get("job_title"),
            email=primary_email,
            phone=primary_phone,
            linkedin_url=row.get("linkedin_url"),
            company_name=row.get("job_company_name"),
            company_domain=row.get("job_company_website"),
        )
