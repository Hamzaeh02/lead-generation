"""Apollo.io people search (person discovery / decision-maker lookup).

Same caveat as `lead_sources/apollo_provider.py`: built from documented
Apollo API conventions, not verified against a live account in this
environment. Verify field mappings once a real APOLLO_API_KEY is in use.

Requires APOLLO_API_KEY.
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

_BASE_URL = "https://api.apollo.io"


class ApolloPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "apollo"
    category = ProviderCategory.PERSON_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("apollo: APOLLO_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        body = self._base_body(criteria)
        payload = await self._search(body)
        people = payload.get("people") or []
        return [self._to_contact(p) for p in people[: criteria.limit]]

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        body: dict = {
            "page": 1,
            "per_page": 25,
            "q_organization_domains": [company_domain],
        }
        if target_titles:
            body["person_titles"] = target_titles
        payload = await self._search(body)
        people = payload.get("people") or []
        return [self._to_contact(p) for p in people]

    async def _search(self, body: dict) -> dict:
        return await request_json(
            self._client,
            "POST",
            "/v1/mixed_people/search",
            provider=self.name,
            headers={"x-api-key": self._api_key},
            json=body,
        )

    def _base_body(self, criteria: DiscoveryCriteria) -> dict:
        body: dict = {"page": 1, "per_page": min(criteria.limit, 100)}
        if criteria.domain:
            body["q_organization_domains"] = [criteria.domain]
        if criteria.job_titles:
            body["person_titles"] = criteria.job_titles
        if criteria.seniorities:
            body["person_seniorities"] = criteria.seniorities
        if criteria.keywords:
            body["q_keywords"] = criteria.keywords
        locations = [p for p in (criteria.city, criteria.state, criteria.country) if p]
        if locations:
            body["person_locations"] = [", ".join(locations)]
        return body

    def _to_contact(self, person: dict) -> NormalizedContact:
        org = person.get("organization") or {}
        return NormalizedContact(
            email=self._real_email_or_none(person.get("email")),
            phone=self._first_phone_number(person),
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=person.get("id"),
                source_url=person.get("linkedin_url"),
                source_type="api",
                raw_reference=person,
            ),
            first_name=person.get("first_name"),
            last_name=person.get("last_name"),
            full_name=person.get("name"),
            job_title=person.get("title"),
            seniority=person.get("seniority"),
            linkedin_url=person.get("linkedin_url"),
            company_name=org.get("name"),
            company_domain=org.get("primary_domain"),
        )

    @staticmethod
    def _real_email_or_none(email: str | None) -> str | None:
        """Apollo returns a literal 'email_not_unlocked@domain.com' placeholder
        when the address hasn't been unlocked with reveal credits — that is
        not a real discovered email and must never be stored as one."""
        if not email or email.startswith("email_not_unlocked"):
            return None
        return email

    @staticmethod
    def _first_phone_number(person: dict) -> str | None:
        """Apollo returns `phone_numbers` as a list of
        {raw_number, sanitized_number, type, ...} objects; take the first
        entry's sanitized (E.164-style) number, falling back to raw."""
        numbers = person.get("phone_numbers")
        if not isinstance(numbers, list) or not numbers:
            return None
        first = numbers[0]
        if not isinstance(first, dict):
            return None
        return first.get("sanitized_number") or first.get("raw_number")
