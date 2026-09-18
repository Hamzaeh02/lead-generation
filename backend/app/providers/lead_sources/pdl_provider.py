"""People Data Labs company search (company discovery).

Built against PDL's documented v5 API (`X-Api-Key` header, SQL-style
`/v5/company/search` search interface). NOTE: not exercised against a live
PDL account in this environment (no network access, no API key) — verify
field mappings in `_to_company` once a real PDL_API_KEY is in use.

Requires PDL_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.http import request_json
from app.providers.lead_sources.base import CompanyDiscoveryProvider

_BASE_URL = "https://api.peopledatalabs.com"


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


class PeopleDataLabsCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "people_data_labs"
    category = ProviderCategory.COMPANY_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("people_data_labs: PDL_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        clauses: list[str] = []
        if criteria.company_name:
            clauses.append(f"name='{_sql_quote(criteria.company_name)}'")
        if criteria.industry:
            clauses.append(f"industry='{_sql_quote(criteria.industry)}'")
        if criteria.domain:
            clauses.append(f"website='{_sql_quote(criteria.domain)}'")
        if criteria.country:
            clauses.append(f"location.country='{_sql_quote(criteria.country)}'")
        if criteria.state:
            clauses.append(f"location.region='{_sql_quote(criteria.state)}'")
        if criteria.employee_count_min is not None:
            clauses.append(f"employee_count>={criteria.employee_count_min}")
        if criteria.employee_count_max is not None:
            clauses.append(f"employee_count<={criteria.employee_count_max}")

        sql = "SELECT * FROM company"
        if clauses:
            sql += f" WHERE {' AND '.join(clauses)}"
        payload = await request_json(
            self._client,
            "POST",
            "/v5/company/search",
            provider=self.name,
            headers={"X-Api-Key": self._api_key},
            json={"sql": sql, "size": criteria.limit},
        )

        rows = payload.get("data") or []
        return [self._to_company(row) for row in rows[: criteria.limit]]

    def _to_company(self, row: dict) -> NormalizedCompany:
        location = row.get("location") or {}
        return NormalizedCompany(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=row.get("id"),
                source_url=row.get("linkedin_url"),
                source_type="api",
                raw_reference=row,
            ),
            name=row.get("name"),
            domain=row.get("website"),
            website=row.get("website"),
            city=location.get("locality"),
            state=location.get("region"),
            country=location.get("country"),
            industry=row.get("industry"),
            employee_count=row.get("employee_count"),
            description=row.get("summary"),
            linkedin_url=row.get("linkedin_url"),
        )
