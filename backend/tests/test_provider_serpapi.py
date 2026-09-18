import httpx
import pytest

from app.providers.base import DiscoveryCriteria
from app.providers.lead_sources.serpapi_provider import SerpApiLocalBusinessProvider

pytestmark = pytest.mark.asyncio


def _mock_transport(payload: dict, *, expected_params: dict | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if expected_params:
            for key, value in expected_params.items():
                assert request.url.params.get(key) == value
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


async def test_discover_local_businesses_maps_fields():
    payload = {
        "local_results": [
            {
                "title": "Acme Dental Group",
                "place_id": "place-123",
                "website": "https://acmedental.example",
                "phone": "+1 555-010-0001",
                "address": "123 Main St, Miami, FL",
                "type": "Dental clinic",
                "gps_coordinates": {"latitude": 25.7, "longitude": -80.1},
            }
        ]
    }
    client = httpx.AsyncClient(
        base_url="https://serpapi.com",
        transport=_mock_transport(payload, expected_params={"engine": "google_maps"}),
    )
    provider = SerpApiLocalBusinessProvider(api_key="test-key", client=client)

    results = await provider.discover_local_businesses(
        DiscoveryCriteria(industry="dental clinics", city="Miami", state="FL", limit=10)
    )

    assert len(results) == 1
    company = results[0]
    assert company.name == "Acme Dental Group"
    assert company.website == "https://acmedental.example"
    assert company.phone == "+1 555-010-0001"
    assert company.category == "Dental clinic"
    assert company.metadata.provider == "serpapi"
    assert company.metadata.external_id == "place-123"


async def test_discover_local_businesses_handles_empty_results():
    client = httpx.AsyncClient(
        base_url="https://serpapi.com", transport=_mock_transport({"local_results": []})
    )
    provider = SerpApiLocalBusinessProvider(api_key="test-key", client=client)

    results = await provider.discover_local_businesses(DiscoveryCriteria(city="Nowhere"))

    assert results == []


async def test_missing_api_key_raises_immediately():
    from app.providers.base import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        SerpApiLocalBusinessProvider(api_key="")


async def test_auth_failure_raises_provider_unavailable():
    from app.providers.base import ProviderUnavailableError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = httpx.AsyncClient(
        base_url="https://serpapi.com", transport=httpx.MockTransport(handler)
    )
    provider = SerpApiLocalBusinessProvider(api_key="bad-key", client=client)

    with pytest.raises(ProviderUnavailableError):
        await provider.discover_local_businesses(DiscoveryCriteria(city="Miami"))
