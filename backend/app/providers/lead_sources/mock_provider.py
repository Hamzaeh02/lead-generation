"""Development/test-only fixture provider.

Returns hard-coded, clearly-labeled fixture data (environment="development")
so the discovery -> normalization -> dedup -> provenance pipeline can be
exercised without a real provider integration. Must never be enabled in
production (see ProviderConfig.category routing in later phases).
"""
from __future__ import annotations

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
)
from app.providers.lead_sources.base import CompanyDiscoveryProvider

_FIXTURES: list[dict] = [
    {
        "external_id": "mock-company-1",
        "name": "Acme Dental Group",
        "domain": "acmedental.example",
        "website": "https://acmedental.example",
        "phone": "+1-555-010-0001",
        "city": "Miami",
        "state": "FL",
        "country": "US",
        "industry": "dental",
        "employee_count": 12,
    },
    {
        "external_id": "mock-company-2",
        "name": "Sunshine Roofing Co",
        "domain": "sunshineroofing.example",
        "website": "https://sunshineroofing.example",
        "phone": "+1-555-010-0002",
        "city": "Dallas",
        "state": "TX",
        "country": "US",
        "industry": "roofing",
        "employee_count": 34,
    },
]


class MockCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "mock_company_discovery"
    category = ProviderCategory.COMPANY_DISCOVERY

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        results: list[NormalizedCompany] = []
        for row in _FIXTURES:
            if criteria.industry and criteria.industry.lower() != row["industry"]:
                continue
            if criteria.state and criteria.state.lower() != row["state"].lower():
                continue
            results.append(
                NormalizedCompany(
                    metadata=ProviderMetadata(
                        provider=self.name,
                        external_id=row["external_id"],
                        source_type="mock_fixture",
                        raw_reference={"environment": "development", **row},
                    ),
                    name=row["name"],
                    domain=row["domain"],
                    website=row["website"],
                    phone=row["phone"],
                    city=row["city"],
                    state=row["state"],
                    country=row["country"],
                    industry=row["industry"],
                    employee_count=row["employee_count"],
                )
            )
        return results[: criteria.limit]
