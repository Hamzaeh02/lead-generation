import httpx
import pytest

from app.providers.base import DiscoveryCriteria
from app.providers.lead_sources.apollo_provider import ApolloCompanyDiscoveryProvider
from app.providers.people_sources.apollo_provider import ApolloPersonDiscoveryProvider

pytestmark = pytest.mark.asyncio


def _client_with(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "test-key"
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(base_url="https://api.apollo.io", transport=httpx.MockTransport(handler))


async def test_discover_companies_maps_fields():
    payload = {
        "organizations": [
            {
                "id": "org-1",
                "name": "Acme Dental Group",
                "primary_domain": "acmedental.example",
                "website_url": "https://acmedental.example",
                "phone": "+15550100001",
                "city": "Miami",
                "state": "FL",
                "country": "US",
                "industry": "dental",
                "estimated_num_employees": 12,
                "linkedin_url": "https://linkedin.com/company/acme-dental",
            }
        ]
    }
    provider = ApolloCompanyDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_companies(DiscoveryCriteria(industry="dental", state="FL"))

    assert len(results) == 1
    assert results[0].name == "Acme Dental Group"
    assert results[0].domain == "acmedental.example"
    assert results[0].employee_count == 12
    assert results[0].metadata.provider == "apollo"
    assert results[0].metadata.external_id == "org-1"


async def test_discover_people_filters_locked_email_placeholder():
    payload = {
        "people": [
            {
                "id": "person-1",
                "first_name": "Jordan",
                "last_name": "Alvarez",
                "name": "Jordan Alvarez",
                "title": "Owner",
                "email": "email_not_unlocked@acmedental.example",
                "linkedin_url": "https://linkedin.com/in/jordan-alvarez",
                "organization": {"name": "Acme Dental Group", "primary_domain": "acmedental.example"},
            }
        ]
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_decision_makers("acmedental.example", ["Owner"])

    assert len(results) == 1
    assert results[0].email is None  # locked placeholder must never be stored as a real email
    assert results[0].job_title == "Owner"
    assert results[0].company_domain == "acmedental.example"


async def test_discover_people_keeps_real_unlocked_email():
    payload = {
        "people": [
            {
                "id": "person-2",
                "first_name": "Sam",
                "last_name": "Chen",
                "name": "Sam Chen",
                "title": "CEO",
                "email": "sam@sunshineroofing.example",
                "organization": {"name": "Sunshine Roofing Co", "primary_domain": "sunshineroofing.example"},
            }
        ]
    }
    provider = ApolloPersonDiscoveryProvider(api_key="test-key", client=_client_with(payload))

    results = await provider.discover_people(DiscoveryCriteria(job_titles=["CEO"]))

    assert results[0].email == "sam@sunshineroofing.example"


async def test_missing_api_key_raises_immediately():
    from app.providers.base import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        ApolloCompanyDiscoveryProvider(api_key="")
    with pytest.raises(ProviderUnavailableError):
        ApolloPersonDiscoveryProvider(api_key="")
