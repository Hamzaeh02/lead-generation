import pytest

from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory

pytestmark = pytest.mark.asyncio


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
    headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
    workspaces_response = await client.get("/api/v1/workspaces", headers=headers)
    return headers, workspaces_response.json()[0]["id"]


async def test_discover_profile_requires_authentication(client):
    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": "00000000-0000-0000-0000-000000000000", "full_name": "Jordan"},
    )
    assert response.status_code == 401


async def test_discover_profile_rejects_disabled_provider(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": workspace_id, "full_name": "Jordan Alvarez"},
        headers=headers,
    )

    assert response.status_code == 400


async def test_discover_profile_reports_missing_credentials(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    db_session.add(
        ProviderConfig(provider="phantombuster", category=ProviderCategory.SOCIAL_SIGNAL, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": workspace_id, "full_name": "Jordan Alvarez"},
        headers=headers,
    )

    assert response.status_code == 503
    assert "PHANTOMBUSTER" in response.json()["detail"]


async def test_discover_profile_requires_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": "00000000-0000-0000-0000-000000000000", "full_name": "Jordan"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_discover_profile_success(client, db_session, unique_email, monkeypatch):
    from app.providers.base import ProviderMetadata
    from app.providers.social.base import SocialProfile

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="phantombuster", category=ProviderCategory.SOCIAL_SIGNAL, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setenv("PHANTOMBUSTER_API_KEY", "key")
    monkeypatch.setenv("PHANTOMBUSTER_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class _StubProvider:
        async def discover_profile(self, *, full_name, company_domain):
            return SocialProfile(
                platform="linkedin",
                profile_url="https://linkedin.com/in/jordan",
                display_name=full_name,
                headline="Owner",
                metadata=ProviderMetadata(provider="phantombuster"),
            )

    monkeypatch.setattr(
        "app.api.v1.social.PhantomBusterSocialProvider",
        lambda client: _StubProvider(),
    )

    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": workspace_id, "full_name": "Jordan Alvarez"},
        headers=headers,
    )
    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["profile_url"] == "https://linkedin.com/in/jordan"
    assert body["display_name"] == "Jordan Alvarez"

    usage_response = await client.get(
        "/api/v1/providers/usage", params={"category": "social_signal"}, headers=headers
    )
    assert any(r["provider"] == "phantombuster" for r in usage_response.json())


async def test_discover_profile_404_when_not_found(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="phantombuster", category=ProviderCategory.SOCIAL_SIGNAL, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setenv("PHANTOMBUSTER_API_KEY", "key")
    monkeypatch.setenv("PHANTOMBUSTER_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class _StubProviderNoMatch:
        async def discover_profile(self, *, full_name, company_domain):
            return None

    monkeypatch.setattr(
        "app.api.v1.social.PhantomBusterSocialProvider",
        lambda client: _StubProviderNoMatch(),
    )

    response = await client.post(
        "/api/v1/social/discover-profile",
        json={"workspace_id": workspace_id, "full_name": "Nobody"},
        headers=headers,
    )
    get_settings.cache_clear()

    assert response.status_code == 404


async def test_discover_posts_success(client, db_session, unique_email, monkeypatch):
    from app.providers.base import ProviderMetadata
    from app.providers.social.base import SocialPost

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="phantombuster", category=ProviderCategory.SOCIAL_SIGNAL, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setenv("PHANTOMBUSTER_API_KEY", "key")
    monkeypatch.setenv("PHANTOMBUSTER_AGENT_ID", "agent-1")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class _StubProvider:
        async def discover_posts(self, keywords, limit=25):
            return [
                SocialPost(
                    platform="linkedin",
                    post_url="https://linkedin.com/post/1",
                    author_profile_url=None,
                    text="We are hiring!",
                    posted_at=None,
                    metadata=ProviderMetadata(provider="phantombuster"),
                )
            ]

    monkeypatch.setattr(
        "app.api.v1.social.PhantomBusterSocialProvider",
        lambda client: _StubProvider(),
    )

    response = await client.post(
        "/api/v1/social/discover-posts",
        json={"workspace_id": workspace_id, "keywords": "hiring"},
        headers=headers,
    )
    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["post_url"] == "https://linkedin.com/post/1"
