import uuid

import pytest

from app.models.company import Company, CompanySource
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


async def _make_company(db_session, workspace_id, *, name="Acme Dental Group", domain="acmedental.example"):
    company = Company(workspace_id=uuid.UUID(workspace_id), name=name, domain=domain)
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


async def test_company_search_matches_name_and_domain(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    await _make_company(db_session, workspace_id, name="Acme Dental Group", domain="acmedental.example")
    await _make_company(db_session, workspace_id, name="Zenith Roofing", domain="zenithroofing.example")

    response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id, "search": "acme"}, headers=headers
    )
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Acme Dental Group"]

    domain_response = await client.get(
        "/api/v1/companies", params={"workspace_id": workspace_id, "search": "zenithroofing"}, headers=headers
    )
    assert [c["name"] for c in domain_response.json()] == ["Zenith Roofing"]


async def test_company_sources_lists_provenance(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id)
    source = CompanySource(
        company_id=company.id, provider="apollo", external_id="ext-1",
        source_url="https://apollo.io/companies/ext-1", source_type="company_discovery",
        raw_reference={"name": "Acme Dental Group"},
    )
    db_session.add(source)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/companies/{company.id}/sources", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["provider"] == "apollo"


async def test_company_sources_404s_for_missing_company(client, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    response = await client.get(
        f"/api/v1/companies/{uuid.uuid4()}/sources", params={"workspace_id": workspace_id}, headers=headers
    )
    assert response.status_code == 404


async def test_leads_filtered_by_company_id(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company_a = await _make_company(db_session, workspace_id, name="Acme Dental Group", domain="acme.example")
    company_b = await _make_company(db_session, workspace_id, name="Zenith Roofing", domain="zenith.example")

    contact_a = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company_a.id, full_name="Jordan Alvarez")
    contact_b = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company_b.id, full_name="Priya Nandan")
    db_session.add_all([contact_a, contact_b])
    await db_session.commit()

    response = await client.get(
        "/api/v1/leads", params={"workspace_id": workspace_id, "company_id": str(company_a.id)}, headers=headers
    )
    assert response.status_code == 200
    names = [c["full_name"] for c in response.json()]
    assert names == ["Jordan Alvarez"]


async def test_lead_response_includes_company_name(client, db_session, unique_email):
    """Regression test: ContactRead.company_name reads a model @property
    that touches the `company` relationship — this must not crash with
    MissingGreenlet on an unloaded relationship, and must actually resolve
    the real name when the repository eager-loads it (see get_by_id)."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    company = await _make_company(db_session, workspace_id, name="Acme Dental Group", domain="acme.example")
    contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=company.id, full_name="Jordan Alvarez")
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)

    detail_response = await client.get(
        f"/api/v1/leads/{contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["company_name"] == "Acme Dental Group"

    list_response = await client.get("/api/v1/leads", params={"workspace_id": workspace_id}, headers=headers)
    assert list_response.status_code == 200
    assert any(c["company_name"] == "Acme Dental Group" for c in list_response.json())

    orphan_contact = Contact(workspace_id=uuid.UUID(workspace_id), company_id=None, full_name="No Company")
    db_session.add(orphan_contact)
    await db_session.commit()
    await db_session.refresh(orphan_contact)

    orphan_response = await client.get(
        f"/api/v1/leads/{orphan_contact.id}", params={"workspace_id": workspace_id}, headers=headers
    )
    assert orphan_response.json()["company_name"] is None
