import pytest
from sqlalchemy import select

from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _register(client, unique_email):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Agency",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _make_superuser(db_session, unique_email):
    user = (await db_session.execute(select(User).where(User.email == unique_email))).scalar_one()
    user.is_superuser = True
    await db_session.commit()


async def test_list_actor_configs_requires_authentication(client):
    response = await client.get("/api/v1/apify/actors")
    assert response.status_code == 401


async def test_non_superuser_cannot_create_actor_config(client, unique_email):
    headers = await _register(client, unique_email)
    response = await client.post(
        "/api/v1/apify/actors",
        json={
            "actor_name": "Google Maps Scraper",
            "actor_id": "actor-123",
            "category": "local_business_discovery",
        },
        headers=headers,
    )
    assert response.status_code == 403


async def test_superuser_can_create_and_update_actor_config(client, db_session, unique_email):
    headers = await _register(client, unique_email)
    await _make_superuser(db_session, unique_email)

    create_response = await client.post(
        "/api/v1/apify/actors",
        json={
            "actor_name": "Google Maps Scraper",
            "actor_id": "actor-123",
            "category": "local_business_discovery",
            "priority": 5,
            "input_schema": {"country": "US"},
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["enabled"] is False
    assert body["input_schema"] == {"country": "US"}

    update_response = await client.patch(
        f"/api/v1/apify/actors/{body['id']}",
        json={"enabled": True, "priority": 1},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["enabled"] is True
    assert updated["priority"] == 1

    list_response = await client.get("/api/v1/apify/actors", headers=headers)
    assert any(a["actor_id"] == "actor-123" for a in list_response.json())


async def test_update_missing_actor_config_returns_404(client, db_session, unique_email):
    headers = await _register(client, unique_email)
    await _make_superuser(db_session, unique_email)

    response = await client.patch(
        "/api/v1/apify/actors/00000000-0000-0000-0000-000000000000",
        json={"enabled": True},
        headers=headers,
    )
    assert response.status_code == 404
