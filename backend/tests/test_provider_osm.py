import httpx
import pytest

from app.providers.base import DiscoveryCriteria
from app.providers.lead_sources.osm_provider import OSMLocalBusinessProvider

pytestmark = pytest.mark.asyncio


def _routed_transport(nominatim_response: httpx.Response, overpass_response: httpx.Response) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in str(request.url):
            return nominatim_response
        return overpass_response

    return httpx.MockTransport(handler)


async def test_discover_local_businesses_uses_known_tag_mapping():
    nominatim_response = httpx.Response(
        200, json=[{"boundingbox": ["25.7", "25.9", "-80.3", "-80.1"]}]
    )
    overpass_response = httpx.Response(
        200,
        json={
            "elements": [
                {
                    "type": "node",
                    "id": 123,
                    "tags": {
                        "name": "Acme Dental Group",
                        "amenity": "dentist",
                        "phone": "+15550100001",
                        "website": "https://acmedental.example",
                        "addr:city": "Miami",
                        "addr:state": "FL",
                    },
                }
            ]
        },
    )
    provider = OSMLocalBusinessProvider(
        client=httpx.AsyncClient(transport=_routed_transport(nominatim_response, overpass_response))
    )

    results = await provider.discover_local_businesses(
        DiscoveryCriteria(industry="dentist", city="Miami", state="FL", limit=10)
    )

    assert len(results) == 1
    assert results[0].name == "Acme Dental Group"
    assert results[0].phone == "+15550100001"
    assert results[0].category == "dentist"
    assert results[0].metadata.provider == "openstreetmap"
    assert results[0].metadata.external_id == "node/123"


async def test_discover_local_businesses_falls_back_to_name_search_for_unknown_industry():
    from urllib.parse import parse_qs

    captured_queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in str(request.url):
            return httpx.Response(200, json=[{"boundingbox": ["25.7", "25.9", "-80.3", "-80.1"]}])
        form = parse_qs(request.content.decode())
        captured_queries.append(form["data"][0])
        return httpx.Response(200, json={"elements": []})

    provider = OSMLocalBusinessProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    await provider.discover_local_businesses(
        DiscoveryCriteria(industry="software agency", city="Austin", state="TX")
    )

    assert any('"name"~"software agency"' in q for q in captured_queries)


async def test_discover_local_businesses_returns_empty_without_location():
    provider = OSMLocalBusinessProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[]))))

    results = await provider.discover_local_businesses(DiscoveryCriteria(industry="dentist"))

    assert results == []


async def test_discover_local_businesses_returns_empty_when_geocode_finds_nothing():
    provider = OSMLocalBusinessProvider(
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    )

    results = await provider.discover_local_businesses(
        DiscoveryCriteria(industry="dentist", city="Nowhereville")
    )

    assert results == []


async def test_elements_without_name_are_skipped():
    nominatim_response = httpx.Response(200, json=[{"boundingbox": ["25.7", "25.9", "-80.3", "-80.1"]}])
    overpass_response = httpx.Response(200, json={"elements": [{"type": "node", "id": 1, "tags": {}}]})
    provider = OSMLocalBusinessProvider(
        client=httpx.AsyncClient(transport=_routed_transport(nominatim_response, overpass_response))
    )

    results = await provider.discover_local_businesses(DiscoveryCriteria(industry="dentist", city="Miami"))

    assert results == []


async def test_no_api_key_required_to_construct():
    # Unlike every paid provider, this must not raise for missing credentials.
    OSMLocalBusinessProvider()
