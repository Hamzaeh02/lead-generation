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


async def _make_contact(db_session, workspace_id, *, full_name="Jordan Alvarez", email="jordan@acmedental.example"):
    company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group")
    db_session.add(company)
    await db_session.flush()
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, full_name=full_name, email=email)
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


async def test_new_lead_defaults_to_new_status(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.json()["status"] == "new"


async def test_update_lead_status(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    response = await client.patch(
        f"/api/v1/leads/{contact.id}/status",
        params={"workspace_id": workspace_id},
        json={"status": "interested"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "interested"


async def test_bulk_status_update(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact_a = await _make_contact(db_session, workspace_id, email="a@acmedental.example")
    contact_b = await _make_contact(db_session, workspace_id, email="b@acmedental.example")

    response = await client.patch(
        "/api/v1/leads/bulk-status",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact_a.id), str(contact_b.id), str(uuid.uuid4())], "status": "meeting"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"updated": 2, "not_found": 1}


async def test_notes_create_and_list(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    create_response = await client.post(
        f"/api/v1/leads/{contact.id}/notes",
        params={"workspace_id": workspace_id},
        json={"text": "Called, left voicemail"},
        headers=headers,
    )
    assert create_response.status_code == 201
    assert create_response.json()["author_user_id"] is not None

    list_response = await client.get(
        f"/api/v1/leads/{contact.id}/notes", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["text"] == "Called, left voicemail"


async def test_tasks_create_list_and_complete(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_contact(db_session, workspace_id)

    create_response = await client.post(
        f"/api/v1/leads/{contact.id}/tasks",
        params={"workspace_id": workspace_id},
        json={"title": "Follow up next week"},
        headers=headers,
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]
    assert create_response.json()["completed"] is False

    update_response = await client.patch(
        f"/api/v1/leads/{contact.id}/tasks/{task_id}",
        params={"workspace_id": workspace_id},
        json={"completed": True},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["completed"] is True

    list_response = await client.get(
        f"/api/v1/leads/{contact.id}/tasks", params={"workspace_id": workspace_id}, headers=headers
    )
    assert len(list_response.json()) == 1


async def test_tags_create_and_bulk_tag(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact_a = await _make_contact(db_session, workspace_id, email="a@acmedental.example")
    contact_b = await _make_contact(db_session, workspace_id, email="b@acmedental.example")

    tag_response = await client.post(
        "/api/v1/tags", params={"workspace_id": workspace_id}, json={"name": "hot-lead"}, headers=headers
    )
    assert tag_response.status_code == 201
    tag_id = tag_response.json()["id"]

    duplicate_response = await client.post(
        "/api/v1/tags", params={"workspace_id": workspace_id}, json={"name": "hot-lead"}, headers=headers
    )
    assert duplicate_response.status_code == 409

    bulk_tag_response = await client.post(
        "/api/v1/leads/bulk-tag",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact_a.id), str(contact_b.id)], "tag_id": tag_id},
        headers=headers,
    )
    assert bulk_tag_response.json() == {"tagged": 2, "already_tagged": 0, "not_found": 0}

    # Re-tagging is idempotent, not double-counted.
    retag_response = await client.post(
        "/api/v1/leads/bulk-tag",
        params={"workspace_id": workspace_id},
        json={"contact_ids": [str(contact_a.id)], "tag_id": tag_id},
        headers=headers,
    )
    assert retag_response.json() == {"tagged": 0, "already_tagged": 1, "not_found": 0}

    filtered_response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id, "tag_id": tag_id}, headers=headers
    )
    assert len(filtered_response.json()) == 2


async def test_lead_list_search_filters_by_text(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    await _make_contact(db_session, workspace_id, full_name="Jordan Alvarez", email="jordan@acmedental.example")
    await _make_contact(db_session, workspace_id, full_name="Sam Chen", email="sam@sunshineroofing.example")

    response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id, "search": "jordan"}, headers=headers
    )
    results = response.json()
    assert len(results) == 1
    assert results[0]["full_name"] == "Jordan Alvarez"


async def test_lead_list_filters_by_status(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact_a = await _make_contact(db_session, workspace_id, email="a@acmedental.example")
    await _make_contact(db_session, workspace_id, email="b@acmedental.example")

    await client.patch(
        f"/api/v1/leads/{contact_a.id}/status",
        params={"workspace_id": workspace_id},
        json={"status": "won"},
        headers=headers,
    )

    response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id, "status": "won"}, headers=headers
    )
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == str(contact_a.id)


async def test_crm_endpoints_require_workspace_membership(client, unique_email):
    headers, _ = await _register_and_get_workspace(client, unique_email)
    other_workspace_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        "/api/v1/leads", params={"workspace_id": other_workspace_id}, headers=headers
    )
    assert response.status_code == 403


async def test_note_and_task_404_for_unknown_contact(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    fake_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/leads/{fake_id}/notes",
        params={"workspace_id": workspace_id},
        json={"text": "test"},
        headers=headers,
    )
    assert response.status_code == 404
