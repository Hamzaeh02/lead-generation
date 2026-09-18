import pytest

pytestmark = pytest.mark.asyncio


async def test_list_workspaces_returns_owned_workspace(client, unique_email):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": "Acme Inc",
        },
    )
    access_token = register_response.json()["access_token"]

    response = await client.get(
        "/api/v1/workspaces", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Acme Inc"
    assert workspaces[0]["slug"] == "acme-inc"


async def test_list_workspaces_requires_authentication(client):
    response = await client.get("/api/v1/workspaces")
    assert response.status_code == 401
