"""Apollo.io organization search (company discovery).

Built against Apollo's documented REST API conventions (`x-api-key` header,
`/v1/mixed_companies/search` endpoint, `organizations` response array).
NOTE: this has not been exercised against a live Apollo account in this
environment (no network access, no API key) — Apollo's exact field names
have shifted across API versions before. If results look wrong once you
plug in a real APOLLO_API_KEY, check Apollo's current API docs and adjust
the field mapping in `_to_company` accordingly; nothing here should be
trusted as verified-correct until it's been run against a live key.

Requires APOLLO_API_KEY.
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

_BASE_URL = "https://api.apollo.io"


class ApolloCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "apollo"
    category = ProviderCategory.COMPANY_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("apollo: APOLLO_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        body: dict = {"page": 1, "per_page": min(criteria.limit, 100)}
        if criteria.company_name:
            body["q_organization_name"] = criteria.company_name
        if criteria.keywords:
            body["q_keywords"] = criteria.keywords
        locations = [p for p in (criteria.city, criteria.state, criteria.country) if p]
        if locations:
            body["organization_locations"] = [", ".join(locations)]
        if criteria.employee_count_min is not None or criteria.employee_count_max is not None:
            lo = criteria.employee_count_min or 1
            hi = criteria.employee_count_max or 1_000_000
            body["organization_num_employees_ranges"] = [f"{lo},{hi}"]

        payload = await request_json(
            self._client,
            "POST",
            "/v1/mixed_companies/search",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json=body,
        )

        organizations = payload.get("organizations") or []
        return [self._to_company(org) for org in organizations[: criteria.limit]]

    def _to_company(self, org: dict) -> NormalizedCompany:
        return NormalizedCompany(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=org.get("id"),
                source_url=org.get("linkedin_url"),
                source_type="api",
                raw_reference=org,
            ),
            name=org.get("name"),
            domain=org.get("primary_domain"),
            website=org.get("website_url"),
            phone=org.get("phone"),
            city=org.get("city"),
            state=org.get("state"),
            country=org.get("country"),
            industry=org.get("industry"),
            employee_count=org.get("estimated_num_employees"),
            description=org.get("short_description"),
            linkedin_url=org.get("linkedin_url"),
        )
