import uuid

import pytest

from app.models.company import Company

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


async def _make_company(db_session, workspace_id):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", domain="acmedental.example")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


async def test_create_intent_signal_requires_source_url(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    response = await client.post(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": workspace_id},
        json={"signal_type": "hiring", "source": "linkedin"},
        headers=headers,
    )

    assert response.status_code == 422  # source_url is a required field


async def test_create_and_list_intent_signals(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    create_response = await client.post(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": workspace_id},
        json={
            "signal_type": "hiring",
            "source": "linkedin",
            "source_url": "https://linkedin.com/jobs/123",
            "signal_text": "Hiring a React developer",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["provider"] == "manual"
    assert body["signal_type"] == "hiring"

    list_response = await client.get(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_intent_score_reflects_signals(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    await client.post(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": workspace_id},
        json={
            "signal_type": "service_request",
            "source": "reddit",
            "source_url": "https://reddit.com/r/x/comments/1",
        },
        headers=headers,
    )

    score_response = await client.get(
        f"/api/v1/companies/{company.id}/intent-score",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert score_response.status_code == 200
    body = score_response.json()
    assert body["score"] == 30
    assert body["signal_count"] == 1


async def test_intent_score_with_no_signals_is_zero(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    response = await client.get(
        f"/api/v1/companies/{company.id}/intent-score",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["score"] == 0


async def test_intent_signal_endpoints_404_for_unknown_company(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    fake_company_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/companies/{fake_company_id}/intent-score",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert response.status_code == 404


async def test_intent_signal_endpoints_require_workspace_membership(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)
    other_workspace_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": other_workspace_id},
        headers=headers,
    )
    assert response.status_code == 403


async def test_intent_signal_endpoints_require_authentication(client):
    response = await client.get(
        f"/api/v1/companies/{uuid.uuid4()}/intent-signals",
        params={"workspace_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


async def test_invalid_signal_type_rejected(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)

    response = await client.post(
        f"/api/v1/companies/{company.id}/intent-signals",
        params={"workspace_id": workspace_id},
        json={
            "signal_type": "not_a_real_type",
            "source": "linkedin",
            "source_url": "https://linkedin.com/jobs/123",
        },
        headers=headers,
    )
    assert response.status_code == 422
