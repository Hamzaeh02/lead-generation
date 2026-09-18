"""Development/test-only fixture provider. See lead_sources/mock_provider.py."""
from __future__ import annotations

from app.providers.base import DiscoveryCriteria, NormalizedContact, ProviderCategory, ProviderMetadata
from app.providers.people_sources.base import PersonDiscoveryProvider

_FIXTURES: list[dict] = [
    {
        "external_id": "mock-person-1",
        "first_name": "Jordan",
        "last_name": "Alvarez",
        "job_title": "Owner",
        "company_domain": "acmedental.example",
        "company_name": "Acme Dental Group",
    },
    {
        "external_id": "mock-person-2",
        "first_name": "Sam",
        "last_name": "Chen",
        "job_title": "CEO",
        "company_domain": "sunshineroofing.example",
        "company_name": "Sunshine Roofing Co",
    },
]


class MockPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "mock_person_discovery"
    category = ProviderCategory.PERSON_DISCOVERY

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        return [self._to_contact(row) for row in _FIXTURES][: criteria.limit]

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        lowered_titles = {t.lower() for t in target_titles}
        matches = [
            row
            for row in _FIXTURES
            if row["company_domain"] == company_domain
            and (not lowered_titles or row["job_title"].lower() in lowered_titles)
        ]
        return [self._to_contact(row) for row in matches]

    def _to_contact(self, row: dict) -> NormalizedContact:
        return NormalizedContact(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=row["external_id"],
                source_type="mock_fixture",
                raw_reference={"environment": "development", **row},
            ),
            first_name=row["first_name"],
            last_name=row["last_name"],
            full_name=f"{row['first_name']} {row['last_name']}",
            job_title=row["job_title"],
            company_domain=row["company_domain"],
            company_name=row["company_name"],
        )
