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


async def test_create_additional_workspace_makes_creator_owner(client, unique_email):
    headers, _first_workspace_id = await _register(client, unique_email)

    response = await client.post(
        "/api/v1/workspaces", json={"name": "Client B"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Client B"
    assert body["plan"] == "free"
    assert body["limits"] == {}

    members = (
        await client.get(f"/api/v1/workspaces/{body['id']}/members", headers=headers)
    ).json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


async def test_update_workspace_plan_and_limits_requires_owner(client, unique_email):
    headers, workspace_id = await _register(client, unique_email)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"plan": "starter", "limits": {"max_team_members": 2}},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "starter"
    assert body["limits"] == {"max_team_members": 2}


async def test_add_member_requires_existing_registered_user(client, unique_email):
    headers, workspace_id = await _register(client, unique_email)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "nobody@example.com", "role": "member"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_add_member_enforces_max_team_members_limit(client, unique_email):
    headers, workspace_id = await _register(client, unique_email)
    other_email = f"other-{unique_email}"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": other_email,
            "password": "S3curePassw0rd!",
            "full_name": "Other User",
            "workspace_name": "Other Co",
        },
    )

    await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"limits": {"max_team_members": 1}},
        headers=headers,
    )

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": other_email, "role": "member"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "limit" in response.json()["detail"].lower()


async def test_add_update_and_remove_member_flow(client, unique_email):
    headers, workspace_id = await _register(client, unique_email)
    other_email = f"member-{unique_email}"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": other_email,
            "password": "S3curePassw0rd!",
            "full_name": "Member User",
            "workspace_name": "Ignored Co",
        },
    )

    add_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": other_email, "role": "viewer"},
        headers=headers,
    )
    assert add_response.status_code == 201
    member = add_response.json()
    assert member["role"] == "viewer"
    assert member["email"] == other_email

    duplicate_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": other_email, "role": "member"},
        headers=headers,
    )
    assert duplicate_response.status_code == 409

    update_response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member['id']}",
        json={"role": "admin"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "admin"

    delete_response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member['id']}", headers=headers
    )
    assert delete_response.status_code == 204

    members = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=headers)
    ).json()
    assert len(members) == 1


async def test_cannot_demote_or_remove_the_only_owner(client, unique_email):
    headers, workspace_id = await _register(client, unique_email)
    members = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=headers)
    ).json()
    owner_member_id = members[0]["id"]

    demote_response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}",
        json={"role": "admin"},
        headers=headers,
    )
    assert demote_response.status_code == 400

    remove_response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}", headers=headers
    )
    assert remove_response.status_code == 400


async def test_viewer_cannot_add_members_only_admin_can(client, unique_email):
    owner_headers, workspace_id = await _register(client, unique_email)
    viewer_email = f"viewer-{unique_email}"
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
    viewer_login = await client.post(
        "/api/v1/auth/login", json={"email": viewer_email, "password": "S3curePassw0rd!"}
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

    third_email = f"third-{unique_email}"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": third_email,
            "password": "S3curePassw0rd!",
            "full_name": "Third User",
            "workspace_name": "Ignored Co 2",
        },
    )
    forbidden_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": third_email, "role": "member"},
        headers=viewer_headers,
    )
    assert forbidden_response.status_code == 403
    assert add_response.status_code == 201
