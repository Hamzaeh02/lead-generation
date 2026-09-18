import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email, workspace_name="Acme Inc"):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "S3curePassw0rd!",
            "full_name": "Test User",
            "workspace_name": workspace_name,
        },
    )
    body = response.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    workspaces = (await client.get("/api/v1/workspaces", headers=headers)).json()
    return headers, workspaces[0]["id"]


async def _add_viewer(client, owner_headers, workspace_id, viewer_email):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": viewer_email,
            "password": "S3curePassw0rd!",
            "full_name": "Viewer User",
            "workspace_name": "Ignored Co",
        },
    )
    add_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": viewer_email, "role": "viewer"},
        headers=owner_headers,
    )
    assert add_response.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": viewer_email, "password": "S3curePassw0rd!"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_viewer_cannot_create_campaign(client, unique_email):
    owner_headers, workspace_id = await _register(client, unique_email)
    viewer_headers = await _add_viewer(client, owner_headers, workspace_id, f"viewer-{unique_email}")

    response = await client.post(
        "/api/v1/campaigns",
        params={"workspace_id": workspace_id},
        json={"name": "Q1 Outreach", "from_email": "agency@example.com", "daily_limit": 50},
        headers=viewer_headers,
    )
    assert response.status_code == 403


async def test_viewer_can_still_list_campaigns(client, unique_email):
    owner_headers, workspace_id = await _register(client, unique_email)
    viewer_headers = await _add_viewer(client, owner_headers, workspace_id, f"viewer-{unique_email}")

    response = await client.get(
        "/api/v1/campaigns", params={"workspace_id": workspace_id}, headers=viewer_headers
    )
    assert response.status_code == 200


async def test_viewer_cannot_create_suppression(client, unique_email):
    owner_headers, workspace_id = await _register(client, unique_email)
    viewer_headers = await _add_viewer(client, owner_headers, workspace_id, f"viewer-{unique_email}")

    response = await client.post(
        "/api/v1/suppressions",
        params={"workspace_id": workspace_id},
        json={"email": "blocked@example.com"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


async def test_member_can_create_suppression(client, unique_email):
    owner_headers, workspace_id = await _register(client, unique_email)
    member_email = f"member-{unique_email}"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "password": "S3curePassw0rd!",
            "full_name": "Member User",
            "workspace_name": "Ignored Co",
        },
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": member_email, "role": "member"},
        headers=owner_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": member_email, "password": "S3curePassw0rd!"}
    )
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        "/api/v1/suppressions",
        params={"workspace_id": workspace_id},
        json={"email": "blocked@example.com"},
        headers=member_headers,
    )
    assert response.status_code == 201
