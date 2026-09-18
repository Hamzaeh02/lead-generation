import httpx
import pytest

from app.models.actor_config import ActorConfig
from app.providers.base import DiscoveryCriteria, ProviderCategory, ProviderUnavailableError
from app.providers.lead_sources.apify_provider import (
    ApifyClient,
    ApifyCompanyDiscoveryProvider,
    ApifyLocalBusinessDiscoveryProvider,
    normalize_dataset,
)

pytestmark = pytest.mark.asyncio


def _actor_config(**overrides) -> ActorConfig:
    defaults = dict(
        actor_name="Google Maps Scraper",
        actor_id="actor-123",
        category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
        enabled=True,
        priority=1,
        input_schema={},
    )
    defaults.update(overrides)
    return ActorConfig(**defaults)


def _sequenced_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return response

    return httpx.MockTransport(handler)


async def test_normalize_dataset_maps_common_field_aliases():
    items = [
        {"title": "Acme Dental Group", "website": "https://acmedental.example", "phone": "+15550100001", "address": "Miami, FL", "type": "Dental clinic"},
        {"companyName": "Sunshine Roofing", "url": "https://sunshine.example"},
        "not-a-dict",
    ]
    results = normalize_dataset(items, provider_name="apify", run_id="run-1")

    assert len(results) == 2
    assert results[0].name == "Acme Dental Group"
    assert results[0].website == "https://acmedental.example"
    assert results[0].category == "Dental clinic"
    assert results[1].name == "Sunshine Roofing"
    assert results[1].website == "https://sunshine.example"


async def test_run_and_collect_full_cycle():
    run_response = httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
    poll_response = httpx.Response(
        200, json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}
    )
    dataset_response = httpx.Response(200, json=[{"title": "Acme Dental Group"}])

    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(
            base_url="https://api.apify.com",
            transport=_sequenced_transport([run_response, poll_response, dataset_response]),
        ),
        poll_interval_seconds=0,
    )

    items, run_id = await client.run_and_collect("actor-123", {"search": "dental"})

    assert run_id == "run-1"
    assert items == [{"title": "Acme Dental Group"}]


async def test_poll_actor_raises_on_failed_status():
    run_response = httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
    failed_response = httpx.Response(200, json={"data": {"id": "run-1", "status": "FAILED"}})

    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(
            base_url="https://api.apify.com",
            transport=_sequenced_transport([run_response, failed_response]),
        ),
        poll_interval_seconds=0,
    )

    with pytest.raises(ProviderUnavailableError):
        await client.run_and_collect("actor-123", {})


async def test_poll_actor_gives_up_after_max_attempts():
    running_response = httpx.Response(200, json={"data": {"id": "run-1", "status": "RUNNING"}})

    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(
            base_url="https://api.apify.com", transport=_sequenced_transport([running_response])
        ),
        poll_interval_seconds=0,
        max_poll_attempts=2,
    )

    with pytest.raises(ProviderUnavailableError):
        await client.poll_actor("run-1")


async def test_missing_token_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        ApifyClient(api_token="")


async def test_local_business_discovery_provider_end_to_end():
    run_response = httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
    poll_response = httpx.Response(
        200, json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}
    )
    dataset_response = httpx.Response(
        200, json=[{"title": "Acme Dental Group", "website": "https://acmedental.example"}]
    )
    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(
            base_url="https://api.apify.com",
            transport=_sequenced_transport([run_response, poll_response, dataset_response]),
        ),
        poll_interval_seconds=0,
    )
    provider = ApifyLocalBusinessDiscoveryProvider(actor_config=_actor_config(), client=client)

    results = await provider.discover_local_businesses(
        DiscoveryCriteria(industry="dental", city="Miami", state="FL", limit=5)
    )

    assert len(results) == 1
    assert results[0].name == "Acme Dental Group"
    assert results[0].metadata.provider == "apify"
    assert results[0].metadata.raw_reference["run_id"] == "run-1"


async def test_company_discovery_provider_merges_actor_input_schema_defaults():
    captured_inputs = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/runs"):
            import json

            captured_inputs.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
        if "/actor-runs/" in request.url.path:
            return httpx.Response(
                200,
                json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
            )
        return httpx.Response(200, json=[])

    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(base_url="https://api.apify.com", transport=httpx.MockTransport(handler)),
        poll_interval_seconds=0,
    )
    actor_config = _actor_config(
        category=ProviderCategory.COMPANY_DISCOVERY, input_schema={"country": "US"}
    )
    provider = ApifyCompanyDiscoveryProvider(actor_config=actor_config, client=client)

    await provider.discover_companies(DiscoveryCriteria(industry="dental", limit=5))

    assert captured_inputs[0]["country"] == "US"
    assert captured_inputs[0]["search"] == "dental"
    assert captured_inputs[0]["maxItems"] == 5


async def test_build_input_sets_google_maps_scraper_field_names_too():
    """Regression test: compass/crawler-google-places (the actor registered
    for local_business_discovery) reads searchStringsArray/locationQuery/
    maxCrawledPlacesPerSearch, not search/location/maxItems — verified
    against its live input schema. Both conventions must be set since an
    actor simply ignores keys it doesn't declare."""
    captured_inputs = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/runs"):
            import json

            captured_inputs.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
        if "/actor-runs/" in request.url.path:
            return httpx.Response(
                200,
                json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
            )
        return httpx.Response(200, json=[])

    client = ApifyClient(
        api_token="test-token",
        client=httpx.AsyncClient(base_url="https://api.apify.com", transport=httpx.MockTransport(handler)),
        poll_interval_seconds=0,
    )
    provider = ApifyLocalBusinessDiscoveryProvider(actor_config=_actor_config(), client=client)

    await provider.discover_local_businesses(
        DiscoveryCriteria(industry="dental", city="Miami", state="FL", limit=5)
    )

    sent = captured_inputs[0]
    assert sent["searchStringsArray"] == ["dental"]
    assert sent["locationQuery"] == "Miami, FL"
    assert sent["maxCrawledPlacesPerSearch"] == 5
    # generic keys still present too, for actors that use those instead
    assert sent["search"] == "dental"
    assert sent["location"] == "Miami, FL"
    assert sent["maxItems"] == 5
