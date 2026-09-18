"""OpenStreetMap local-business discovery — genuinely free, no API key.

Uses two public OSM services, neither requiring credentials:
- Nominatim (https://nominatim.org/release-docs/latest/api/Search/) to
  geocode a city/state/country into a bounding box.
- Overpass API (https://wiki.openstreetmap.org/wiki/Overpass_API) to query
  businesses within that box.

Both ask for a descriptive User-Agent and reasonable request rates
(Nominatim: ~1 req/sec) rather than an API key — this client sends one and
relies on ProviderUsageRecorder's normal retry/backoff for rate limits.
Unlike every paid provider in this codebase, this one is never gated by
missing-credentials logic; it's always available.

Industry-to-OSM-tag mapping is necessarily partial (OSM tags physical POI
categories, not arbitrary "industries") — unmapped industries fall back to
a free-text name search within the bounding box.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
)
from app.providers.http import request_json
from app.providers.lead_sources.base import LocalBusinessDiscoveryProvider

_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
_OVERPASS_URL = "https://overpass-api.de"
_USER_AGENT = "lead-intelligence-platform/1.0 (free OSM local-business discovery)"

_INDUSTRY_TAGS: dict[str, tuple[str, str]] = {
    "dentist": ("amenity", "dentist"),
    "dental": ("amenity", "dentist"),
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "coffee": ("amenity", "cafe"),
    "hotel": ("tourism", "hotel"),
    "gym": ("leisure", "fitness_centre"),
    "fitness": ("leisure", "fitness_centre"),
    "roofing": ("craft", "roofer"),
    "roofer": ("craft", "roofer"),
    "plumber": ("craft", "plumber"),
    "plumbing": ("craft", "plumber"),
    "electrician": ("craft", "electrician"),
    "hardware": ("shop", "hardware"),
    "bakery": ("shop", "bakery"),
    "bank": ("amenity", "bank"),
    "pharmacy": ("amenity", "pharmacy"),
    "hairdresser": ("shop", "hairdresser"),
    "salon": ("shop", "hairdresser"),
    "car_repair": ("shop", "car_repair"),
    "auto_repair": ("shop", "car_repair"),
}


class OSMLocalBusinessProvider(LocalBusinessDiscoveryProvider):
    name = "openstreetmap"
    category = ProviderCategory.LOCAL_BUSINESS_DISCOVERY

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), headers={"User-Agent": _USER_AGENT}
        )

    async def discover_local_businesses(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        bbox = await self._geocode(criteria)
        if bbox is None:
            return []

        query = self._build_query(criteria, bbox)
        payload = await request_json(
            self._client,
            "POST",
            f"{_OVERPASS_URL}/api/interpreter",
            provider=self.name,
            data={"data": query},
        )
        elements = payload.get("elements") or []
        companies = [self._to_company(el) for el in elements[: criteria.limit]]
        return [c for c in companies if c is not None]

    async def _geocode(self, criteria: DiscoveryCriteria) -> tuple[float, float, float, float] | None:
        location_parts = [p for p in (criteria.city, criteria.state, criteria.country) if p]
        if not location_parts:
            return None
        results = await request_json(
            self._client,
            "GET",
            f"{_NOMINATIM_URL}/search",
            provider=self.name,
            params={"q": ", ".join(location_parts), "format": "json", "limit": 1},
        )
        if not results:
            return None
        south, north, west, east = (float(x) for x in results[0]["boundingbox"])
        return south, north, west, east

    def _build_query(self, criteria: DiscoveryCriteria, bbox: tuple[float, float, float, float]) -> str:
        south, north, west, east = bbox
        bbox_str = f"{south},{west},{north},{east}"
        subject = (criteria.industry or criteria.keywords or "").strip().lower()
        tag = _INDUSTRY_TAGS.get(subject)
        limit = min(criteria.limit, 100)

        if tag:
            key, value = tag
            tag_filter = f'["{key}"="{value}"]'
        else:
            search_text = subject or (criteria.company_name or "").strip().lower()
            tag_filter = f'["name"~"{search_text}",i]' if search_text else ""

        return (
            "[out:json][timeout:25];"
            f"(node{tag_filter}({bbox_str});way{tag_filter}({bbox_str}););"
            f"out center tags {limit};"
        )

    def _to_company(self, element: dict) -> NormalizedCompany | None:
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            return None

        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
            tags.get("addr:state"),
            tags.get("addr:postcode"),
        ]
        address = " ".join(p for p in address_parts if p) or None

        return NormalizedCompany(
            metadata=ProviderMetadata(
                provider=self.name,
                external_id=f"{element.get('type')}/{element.get('id')}",
                source_type="api",
                raw_reference=element,
            ),
            name=name,
            website=tags.get("website") or tags.get("contact:website"),
            phone=tags.get("phone") or tags.get("contact:phone"),
            address=address,
            city=tags.get("addr:city"),
            state=tags.get("addr:state"),
            country=tags.get("addr:country"),
            postal_code=tags.get("addr:postcode"),
            category=tags.get("amenity") or tags.get("shop") or tags.get("craft") or tags.get("tourism"),
        )
