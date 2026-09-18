import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email: str, password: str = "S3curePassw0rd!", workspace: str = "Acme Inc"):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "workspace_name": workspace,
        },
    )


async def test_register_creates_user_and_workspace(client, unique_email):
    response = await _register(client, unique_email)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == unique_email
    assert "access_token" in body
    assert "refresh_token" in body


async def test_register_duplicate_email_returns_409(client, unique_email):
    await _register(client, unique_email)
    response = await _register(client, unique_email)
    assert response.status_code == 409


async def test_login_with_valid_credentials(client, unique_email):
    await _register(client, unique_email, password="S3curePassw0rd!")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "S3curePassw0rd!"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_with_invalid_password_returns_401(client, unique_email):
    await _register(client, unique_email, password="S3curePassw0rd!")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_refresh_token_issues_new_access_token(client, unique_email):
    register_response = await _register(client, unique_email)
    refresh_token = register_response.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_me_requires_authentication(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client, unique_email):
    register_response = await _register(client, unique_email)
    access_token = register_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == unique_email
