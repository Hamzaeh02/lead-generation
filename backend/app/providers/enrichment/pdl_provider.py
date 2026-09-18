"""People Data Labs company/person enrichment.

Same caveat as the other PDL providers: built from documented v5 API
conventions (`/v5/company/enrich`, `/v5/person/enrich`, GET + query params,
`X-Api-Key` header), not verified against a live account. A PDL enrichment
lookup that finds no match returns HTTP 404 in PDL's API — that is treated
as "no data" (returns None), not an error.

Requires PDL_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    NormalizedCompany,
    NormalizedContact,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.enrichment.base import EnrichmentProvider

_BASE_URL = "https://api.peopledatalabs.com"


class PeopleDataLabsEnrichmentProvider(EnrichmentProvider):
    name = "people_data_labs"
    category = ProviderCategory.ENRICHMENT

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("people_data_labs: PDL_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL, timeout=httpx.Timeout(15.0)
        )

    async def enrich_company(
        self, *, domain: str | None = None, name: str | None = None
    ) -> NormalizedCompany | None:
        if not domain and not name:
            return None
        params = {k: v for k, v in {"website": domain, "name": name}.items() if v}

        response = await self._client.get(
            "/v5/company/enrich", params=params, headers={"X-Api-Key": self._api_key}
        )
        if response.status_code == 404:
            return None
        data = await self._json_or_raise(response)

        row = data.get("data") if isinstance(data.get("data"), dict) else data
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

    async def enrich_person(
        self,
        *,
        email: str | None = None,
        linkedin_url: str | None = None,
        full_name: str | None = None,
        company_domain: str | None = None,
    ) -> NormalizedContact | None:
        if not any((email, linkedin_url, full_name)):
            return None
        params = {
            k: v
            for k, v in {
                "email": email,
                "profile": linkedin_url,
                "name": full_name,
                "company": company_domain,
            }.items()
            if v
        }

        response = await self._client.get(
            "/v5/person/enrich", params=params, headers={"X-Api-Key": self._api_key}
        )
        if response.status_code == 404:
            return None
        data = await self._json_or_raise(response)

        row = data.get("data") if isinstance(data.get("data"), dict) else data
        emails = row.get("emails") or []
        primary_email = emails[0].get("address") if emails and isinstance(emails[0], dict) else None

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
            email=primary_email or email,
            linkedin_url=row.get("linkedin_url"),
            company_name=row.get("job_company_name"),
            company_domain=row.get("job_company_website"),
        )

    async def _json_or_raise(self, response: httpx.Response) -> dict:
        # Reuses request_json's status/JSON handling without re-issuing the request.
        if response.status_code in (401, 403):
            raise ProviderUnavailableError(f"{self.name}: authentication rejected (check API key)")
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                f"{self.name}: request failed with HTTP {response.status_code}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailableError(f"{self.name}: non-JSON response") from exc
