import pytest

from app.models.provider_config import ProviderConfig
from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    ProviderCategory,
    ProviderMetadata,
)
from app.providers.lead_sources.base import CompanyDiscoveryProvider

pytestmark = pytest.mark.asyncio


class _StubCompanyDiscoveryProvider(CompanyDiscoveryProvider):
    name = "stub"
    category = ProviderCategory.COMPANY_DISCOVERY

    async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
        return [
            NormalizedCompany(
                metadata=ProviderMetadata(provider="stub", external_id="stub-1"),
                name="Acme Dental Group",
                domain="acmedental.example",
                city="Miami",
                state="FL",
            )
        ]


async def _register_and_get_workspace(client, unique_email):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Agency",
        },
    )
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    workspaces_response = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces_response.json()[0]["id"]
    return headers, workspace_id


async def test_search_execute_with_stub_provider_persists_results(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubCompanyDiscoveryProvider(),
    )

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {"industry": "dental", "state": "FL"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["companies_created"] == 1
    assert len(body["companies"]) == 1
    assert body["companies"][0]["name"] == "Acme Dental Group"

    companies_response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(companies_response.json()) == 1


async def test_search_execute_matched_company_serializes_correctly(
    client, db_session, unique_email, monkeypatch
):
    """Regression test: a matched (not newly-created) company is mutated
    in-place by the resolver, then returned in the API response. Before the
    post-commit refresh fix, serializing it crashed with MissingGreenlet
    because onupdate=func.now() columns are expired after commit."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubCompanyDiscoveryProvider(),
    )

    payload = {
        "workspace_id": workspace_id,
        "provider": "stub",
        "category": "company_discovery",
        "criteria": {"industry": "dental", "state": "FL"},
    }
    first = await client.post("/api/v1/search/execute", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["companies_created"] == 1

    second = await client.post("/api/v1/search/execute", json=payload, headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["companies_matched"] == 1
    assert body["companies_created"] == 0
    assert body["companies"][0]["name"] == "Acme Dental Group"


async def test_search_execute_rejects_disabled_provider(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apollo",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]


async def test_search_execute_reports_missing_credentials(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="apollo", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1
        )
    )
    await db_session.commit()

    # APOLLO_API_KEY is not set in the test environment, so the registry
    # allows it but the factory can't build a working provider instance.
    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apollo",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 503
    assert "APOLLO_API_KEY" in response.json()["detail"]


async def test_search_execute_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000000",
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 403


async def test_search_execute_requires_authentication(client):
    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": "00000000-0000-0000-0000-000000000000",
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
    )
    assert response.status_code == 401


async def test_search_execute_apify_without_actor_config_returns_400(
    client, db_session, unique_email
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="apify",
            category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
            enabled=True,
            priority=1,
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apify",
            "category": "local_business_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "No enabled Apify actor" in response.json()["detail"]


async def test_search_execute_apify_with_actor_but_no_token_returns_503(
    client, db_session, unique_email, monkeypatch
):
    from app.core.config import get_settings
    from app.models.actor_config import ActorConfig

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="apify",
            category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
            enabled=True,
            priority=1,
        )
    )
    db_session.add(
        ActorConfig(
            actor_name="Google Maps Scraper",
            actor_id="actor-123",
            category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
            enabled=True,
            priority=1,
        )
    )
    await db_session.commit()

    # This test's whole premise is a missing token — force it empty rather
    # than relying on the ambient environment not having one configured
    # (a real deployment's .env may well have a real APIFY_API_TOKEN set).
    monkeypatch.setenv("APIFY_API_TOKEN", "")
    get_settings.cache_clear()

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apify",
            "category": "local_business_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    get_settings.cache_clear()

    assert response.status_code == 503
    assert "APIFY_API_TOKEN" in response.json()["detail"]


async def test_search_execute_apify_full_flow_persists_company(
    client, db_session, unique_email, monkeypatch
):
    import httpx

    from app.models.actor_config import ActorConfig

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(
            provider="apify",
            category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
            enabled=True,
            priority=1,
        )
    )
    db_session.add(
        ActorConfig(
            actor_name="Google Maps Scraper",
            actor_id="actor-123",
            category=ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
            enabled=True,
            priority=1,
        )
    )
    await db_session.commit()

    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/runs"):
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
        if "/actor-runs/" in request.url.path:
            return httpx.Response(
                200,
                json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
            )
        return httpx.Response(200, json=[{"title": "Acme Dental Group"}])

    # Patch ApifyClient construction to inject a mock transport instead of a real client.
    import app.providers.lead_sources.apify_provider as apify_module

    original_init = apify_module.ApifyClient.__init__

    def patched_init(self, *, api_token, client=None, poll_interval_seconds=2.0, max_poll_attempts=30):
        mock_client = httpx.AsyncClient(
            base_url="https://api.apify.com", transport=httpx.MockTransport(handler)
        )
        original_init(
            self,
            api_token=api_token,
            client=mock_client,
            poll_interval_seconds=0,
            max_poll_attempts=max_poll_attempts,
        )

    monkeypatch.setattr(apify_module.ApifyClient, "__init__", patched_init)

    response = await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "apify",
            "category": "local_business_discovery",
            "criteria": {"industry": "dental", "city": "Miami"},
        },
        headers=headers,
    )

    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["companies_created"] == 1
    assert body["companies"][0]["name"] == "Acme Dental Group"
