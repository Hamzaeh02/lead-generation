"""SerpApi local-business discovery (Google Maps search engine).

Docs: https://serpapi.com/google-maps-api — this is SerpApi's stable,
well-documented `local_results` response shape (engine=google_maps).
Requires SERPAPI_API_KEY. Every field below is read defensively (`.get`)
since SerpApi does not guarantee every field is present for every result —
a missing field stays None rather than being guessed at.
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
from app.providers.lead_sources.base import LocalBusinessDiscoveryProvider

_BASE_URL = "https://serpapi.com"


class SerpApiLocalBusinessProvider(LocalBusinessDiscoveryProvider):
    name = "serpapi"
    category = ProviderCategory.LOCAL_BUSINESS_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("serpapi: SERPAPI_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def discover_local_businesses(
        self, criteria: DiscoveryCriteria
    ) -> list[NormalizedCompany]:
        query = self._build_query(criteria)
        params = {
            "engine": "google_maps",
            "type": "search",
            "q": query,
            "api_key": self._api_key,
        }
        payload = await request_json(
            self._client, "GET", "/search.json", provider=self.name, params=params
        )

        results = payload.get("local_results") or []
        if isinstance(results, dict):
            # SerpApi sometimes returns a single dict instead of a list for one result.
            results = [results]

        companies = [self._to_company(row, query) for row in results[: criteria.limit]]
        return companies

    def _build_query(self, criteria: DiscoveryCriteria) -> str:
        subject = criteria.keywords or criteria.industry or criteria.company_name or "businesses"
        location_parts = [p for p in (criteria.city, criteria.state, criteria.country) if p]
        if location_parts:
            return f"{subject} in {', '.join(location_parts)}"
        return subject

    def _to_company(self, row: dict, query: str) -> NormalizedCompany:
        place_id = row.get("place_id")
        gps = row.get("gps_coordinates") or {}
        return NormalizedCompany(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=place_id,
                source_url=row.get("links", {}).get("website")
                if isinstance(row.get("links"), dict)
                else None,
                source_type="api",
                raw_reference={"query": query, "gps_coordinates": gps, **row},
            ),
            name=row.get("title"),
            website=row.get("website"),
            phone=row.get("phone"),
            address=row.get("address"),
            category=row.get("type"),
            description=row.get("description"),
        )
