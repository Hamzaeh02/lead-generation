import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Inc",
        },
    )
    return response.json()


async def test_logout_revokes_access_token(client, unique_email):
    body = await _register(client, unique_email)
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    logout_response = await client.post("/api/v1/auth/logout", json={}, headers=headers)
    assert logout_response.status_code == 204

    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401


async def test_logout_revokes_refresh_token_when_provided(client, unique_email):
    body = await _register(client, unique_email)
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": body["refresh_token"]},
        headers=headers,
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert refresh_response.status_code == 401


async def test_refresh_token_still_works_if_not_sent_to_logout(client, unique_email):
    body = await _register(client, unique_email)
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    await client.post("/api/v1/auth/logout", json={}, headers=headers)

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert refresh_response.status_code == 200


async def test_logout_requires_authentication(client):
    response = await client.post("/api/v1/auth/logout", json={})
    assert response.status_code == 401
