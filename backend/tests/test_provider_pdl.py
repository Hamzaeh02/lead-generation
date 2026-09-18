import httpx
import pytest

from app.providers.base import DiscoveryCriteria
from app.providers.enrichment.pdl_provider import PeopleDataLabsEnrichmentProvider
from app.providers.lead_sources.pdl_provider import PeopleDataLabsCompanyDiscoveryProvider
from app.providers.people_sources.pdl_provider import PeopleDataLabsPersonDiscoveryProvider

pytestmark = pytest.mark.asyncio


def _client_with(payload: dict, *, status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "test-key"
        return httpx.Response(status_code, json=payload)

    return httpx.AsyncClient(
        base_url="https://api.peopledatalabs.com", transport=httpx.MockTransport(handler)
    )


async def test_discover_companies_maps_fields():
    payload = {
        "data": [
            {
                "id": "co-1",
                "name": "Sunshine Roofing Co",
                "website": "sunshineroofing.example",
                "location": {"locality": "Dallas", "region": "TX", "country": "US"},
                "industry": "construction",
                "employee_count": 34,
                "linkedin_url": "https://linkedin.com/company/sunshine-roofing",
            }
        ]
    }
    provider = PeopleDataLabsCompanyDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_companies(DiscoveryCriteria(state="TX"))

    assert len(results) == 1
    assert results[0].name == "Sunshine Roofing Co"
    assert results[0].city == "Dallas"
    assert results[0].employee_count == 34
    assert results[0].metadata.provider == "people_data_labs"


async def test_discover_people_maps_first_email_and_phone():
    payload = {
        "data": [
            {
                "id": "person-1",
                "first_name": "Jordan",
                "last_name": "Alvarez",
                "full_name": "Jordan Alvarez",
                "job_title": "Owner",
                "job_company_name": "Acme Dental Group",
                "job_company_website": "acmedental.example",
                "emails": [{"address": "jordan@acmedental.example", "type": "professional"}],
                "phone_numbers": ["+15550100001"],
            }
        ]
    }
    provider = PeopleDataLabsPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_decision_makers("acmedental.example", ["Owner"])

    assert len(results) == 1
    assert results[0].email == "jordan@acmedental.example"
    assert results[0].phone == "+15550100001"
    assert results[0].company_domain == "acmedental.example"


async def test_enrich_company_returns_none_on_404():
    provider = PeopleDataLabsEnrichmentProvider(
        api_key="test-key", client=_client_with({}, status_code=404)
    )

    result = await provider.enrich_company(domain="unknown.example")

    assert result is None


async def test_enrich_company_maps_fields():
    payload = {
        "data": {
            "id": "co-1",
            "name": "Acme Dental Group",
            "website": "acmedental.example",
            "location": {"locality": "Miami", "region": "FL", "country": "US"},
            "industry": "dental",
        }
    }
    provider = PeopleDataLabsEnrichmentProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.enrich_company(domain="acmedental.example")

    assert result is not None
    assert result.name == "Acme Dental Group"
    assert result.city == "Miami"


async def test_enrich_person_with_no_identifiers_returns_none_without_a_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not make a request with no identifiers")

    client = httpx.AsyncClient(
        base_url="https://api.peopledatalabs.com", transport=httpx.MockTransport(handler)
    )
    provider = PeopleDataLabsEnrichmentProvider(api_key="test-key", client=client)

    result = await provider.enrich_person()

    assert result is None


async def test_missing_api_key_raises_immediately():
    from app.providers.base import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        PeopleDataLabsCompanyDiscoveryProvider(api_key="")
    with pytest.raises(ProviderUnavailableError):
        PeopleDataLabsPersonDiscoveryProvider(api_key="")
    with pytest.raises(ProviderUnavailableError):
        PeopleDataLabsEnrichmentProvider(api_key="")
