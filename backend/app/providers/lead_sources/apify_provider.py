"""Apify actor execution + generic company-shaped dataset normalization.

Apify is not one fixed integration — any actor can be registered via
`ActorConfig` (see app/models/actor_config.py) and run through here. Built
against Apify's documented, stable REST API (`Authorization: Bearer` header,
`/v2/acts/{actorId}/runs`, `/v2/actor-runs/{runId}`,
`/v2/datasets/{datasetId}/items`) — this shape has been stable for years and
I'm confident in it, unlike the Apollo/PDL integrations in Phase 3.

Because actor output schemas vary per-actor, `normalize_dataset` is a
best-effort field-alias mapper (title/name, url/website, phone/phoneNumber,
...), not a guarantee of correct extraction for any given actor — an admin
registering a new actor should sanity-check a real run's output against the
mapping below and adjust it if fields don't line up.

Requires APIFY_API_TOKEN.
"""
from __future__ import annotations

import asyncio

import httpx

from app.models.actor_config import ActorConfig
from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.http import request_json
from app.providers.lead_sources.base import CompanyDiscoveryProvider, LocalBusinessDiscoveryProvider

_BASE_URL = "https://api.apify.com"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}

_NAME_KEYS = ("title", "name", "companyName", "business_name")
_WEBSITE_KEYS = ("website", "url", "domain", "site")
_PHONE_KEYS = ("phone", "phoneNumber", "phone_number")
_ADDRESS_KEYS = ("address", "fullAddress", "formatted_address")
_CATEGORY_KEYS = ("category", "type", "categoryName")
_DESCRIPTION_KEYS = ("description", "summary", "snippet")


def _first(row: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def normalize_dataset(items: list[dict], *, provider_name: str, run_id: str) -> list[NormalizedCompany]:
    companies: list[NormalizedCompany] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        companies.append(
            NormalizedCompany(
                metadata=ProviderMetadata(
                    provider=provider_name,
                    external_id=row.get("id") or row.get("placeId"),
                    source_url=row.get("url"),
                    source_type="apify_actor",
                    raw_reference={"run_id": run_id, **row},
                ),
                name=_first(row, _NAME_KEYS),
                website=_first(row, _WEBSITE_KEYS),
                phone=_first(row, _PHONE_KEYS),
                address=_first(row, _ADDRESS_KEYS),
                category=_first(row, _CATEGORY_KEYS),
                description=_first(row, _DESCRIPTION_KEYS),
            )
        )
    return companies


class ApifyClient:
    def __init__(
        self,
        *,
        api_token: str,
        client: httpx.AsyncClient | None = None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 30,
    ) -> None:
        if not api_token:
            raise ProviderUnavailableError("apify: APIFY_API_TOKEN is not configured")
        self._token = api_token
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(15.0))
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def run_actor(self, actor_id: str, run_input: dict) -> str:
        payload = await request_json(
            self._client,
            "POST",
            f"/v2/acts/{actor_id}/runs",
            provider="apify",
            headers=self._headers(),
            json=run_input,
        )
        run_id = payload.get("data", {}).get("id")
        if not run_id:
            raise ProviderUnavailableError("apify: run response missing run id")
        return run_id

    async def poll_actor(self, run_id: str) -> dict:
        for attempt in range(self._max_poll_attempts):
            payload = await request_json(
                self._client,
                "GET",
                f"/v2/actor-runs/{run_id}",
                provider="apify",
                headers=self._headers(),
            )
            run_data = payload.get("data", {})
            status = run_data.get("status")
            if status in _TERMINAL_STATUSES:
                if status != "SUCCEEDED":
                    raise ProviderUnavailableError(f"apify: run {run_id} ended with status {status}")
                return run_data
            if attempt < self._max_poll_attempts - 1:
                await asyncio.sleep(self._poll_interval_seconds)
        raise ProviderUnavailableError(f"apify: run {run_id} did not complete in time")

    async def retrieve_dataset(self, dataset_id: str) -> list[dict]:
        response = await self._client.get(
            f"/v2/datasets/{dataset_id}/items", headers=self._headers()
        )
        if response.status_code in (401, 403):
            raise ProviderUnavailableError("apify: authentication rejected (check API token)")
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                f"apify: dataset fetch failed with HTTP {response.status_code}"
            )
        items = response.json()
        return items if isinstance(items, list) else []

    async def run_and_collect(self, actor_id: str, run_input: dict) -> tuple[list[dict], str]:
        run_id = await self.run_actor(actor_id, run_input)
        run_data = await self.poll_actor(run_id)
        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            return [], run_id
        items = await self.retrieve_dataset(dataset_id)
        return items, run_id


def _build_input(actor_config: ActorConfig, criteria: DiscoveryCriteria) -> dict:
    """Actor input field names vary per actor (there's no fixed Apify
    input contract), so this sets several common conventions at once
    rather than guessing one — an actor simply ignores keys it doesn't
    declare in its own input schema, so setting extras is harmless. Known
    concretely from compass/crawler-google-places (Google Maps Scraper,
    the actor registered for local_business_discovery): searchStringsArray
    (list), locationQuery (str), maxCrawledPlacesPerSearch (int) — verified
    against its live input schema, not guessed. `actor_config.input_schema`
    values always win (setdefault), so an admin registering a
    differently-shaped actor can override any of these.
    """
    location = ", ".join(p for p in (criteria.city, criteria.state, criteria.country) if p)
    search_term = criteria.keywords or criteria.industry or criteria.company_name

    run_input = dict(actor_config.input_schema)
    run_input.setdefault("search", search_term)
    if search_term:
        run_input.setdefault("searchStringsArray", [search_term])
    if location:
        run_input.setdefault("location", location)
        run_input.setdefault("locationQuery", location)
    run_input.setdefault("maxItems", criteria.limit)
    run_input.setdefault("maxCrawledPlacesPerSearch", criteria.limit)
    return run_input


class ApifyCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "apify"
    category = ProviderCategory.COMPANY_DISCOVERY

    def __init__(self, *, actor_config: ActorConfig, client: ApifyClient) -> None:
        super().__init__()
        self._actor_config = actor_config
        self._client = client

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        run_input = _build_input(self._actor_config, criteria)
        items, run_id = await self._client.run_and_collect(self._actor_config.actor_id, run_input)
        return normalize_dataset(items[: criteria.limit], provider_name=self.name, run_id=run_id)


class ApifyLocalBusinessDiscoveryProvider(LocalBusinessDiscoveryProvider):
    name = "apify"
    category = ProviderCategory.LOCAL_BUSINESS_DISCOVERY

    def __init__(self, *, actor_config: ActorConfig, client: ApifyClient) -> None:
        super().__init__()
        self._actor_config = actor_config
        self._client = client

    async def discover_local_businesses(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        run_input = _build_input(self._actor_config, criteria)
        items, run_id = await self._client.run_and_collect(self._actor_config.actor_id, run_input)
        return normalize_dataset(items[: criteria.limit], provider_name=self.name, run_id=run_id)
