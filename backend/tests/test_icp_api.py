import uuid

import pytest

from app.models.company import Company
from app.models.contact import Contact

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


async def test_parse_nl_icp_requires_authentication(client):
    response = await client.post("/api/v1/icp-profiles/parse", json={"text": "dentists in Florida"})
    assert response.status_code == 401


async def test_parse_nl_icp_returns_suggestion(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)

    response = await client.post(
        "/api/v1/icp-profiles/parse",
        json={"text": "Find dental clinic owners in Florida with 5 to 50 employees."},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggested"]["industry"] == "dental"
    assert body["suggested"]["state"] == "Florida"
    assert body["suggested"]["employee_count_min"] == 5


async def test_create_list_get_update_icp_profile(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    create_response = await client.post(
        "/api/v1/icp-profiles",
        params={"workspace_id": workspace_id},
        json={"name": "Dental Florida", "industry": "dental", "state": "FL"},
        headers=headers,
    )
    assert create_response.status_code == 201
    profile_id = create_response.json()["id"]

    list_response = await client.get(
        "/api/v1/icp-profiles", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(list_response.json()) == 1

    get_response = await client.get(
        f"/api/v1/icp-profiles/{profile_id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Dental Florida"

    update_response = await client.patch(
        f"/api/v1/icp-profiles/{profile_id}",
        params={"workspace_id": workspace_id},
        json={"employee_count_min": 5, "employee_count_max": 50},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["employee_count_min"] == 5
    assert update_response.json()["industry"] == "dental"  # untouched fields preserved


async def test_icp_profile_endpoints_require_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)
    other_workspace_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        "/api/v1/icp-profiles", params={"workspace_id": other_workspace_id}, headers=headers
    )
    assert response.status_code == 403


async def test_get_missing_icp_profile_404s(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    response = await client.get(
        f"/api/v1/icp-profiles/{uuid.uuid4()}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 404


async def test_company_icp_score_endpoint(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)

    company = Company(
        workspace_id=uuid.UUID(workspace_id),
        name="Acme Dental Group",
        industry="dental",
        state="FL",
        employee_count=20,
    )
    db_session.add(company)
    await db_session.flush()
    db_session.add(Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, job_title="Owner"))
    await db_session.commit()

    create_response = await client.post(
        "/api/v1/icp-profiles",
        params={"workspace_id": workspace_id},
        json={"name": "Dental FL", "industry": "dental", "state": "FL", "target_titles": ["Owner"]},
        headers=headers,
    )
    icp_profile_id = create_response.json()["id"]

    score_response = await client.get(
        f"/api/v1/companies/{company.id}/icp-score",
        params={"workspace_id": workspace_id, "icp_profile_id": icp_profile_id},
        headers=headers,
    )

    assert score_response.status_code == 200
    body = score_response.json()
    assert body["score"] == 30 + 25 + 15  # industry + location(state only) + decision-maker
    assert len(body["matched_criteria"]) == 3


async def test_company_icp_score_404s_for_missing_icp_profile(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme")
    db_session.add(company)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/companies/{company.id}/icp-score",
        params={"workspace_id": workspace_id, "icp_profile_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404
