import uuid
from datetime import datetime, timezone

import pytest

from app.models.company import Company
from app.models.contact import Contact
from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory, ProviderMetadata
from app.providers.email_finders.base import EmailCandidate, EmailConfidence, EmailFinderProvider
from app.providers.email_verifiers.base import (
    EmailVerifierProvider,
    VerificationResult,
    VerificationStatus,
)

pytestmark = pytest.mark.asyncio


class _StubEmailFinder(EmailFinderProvider):
    name = "stub"
    category = ProviderCategory.EMAIL_FINDER

    async def find_email(self, *, first_name, last_name, full_name, company_domain):
        return EmailCandidate(
            email=f"{(first_name or 'contact').lower()}@{company_domain}",
            confidence=EmailConfidence.FOUND,
            metadata=ProviderMetadata(provider="stub", retrieved_at=datetime.now(timezone.utc)),
        )


class _StubEmailVerifier(EmailVerifierProvider):
    name = "stub"
    category = ProviderCategory.EMAIL_VERIFIER

    async def verify(self, email):
        return VerificationResult(
            status=VerificationStatus.VALID,
            metadata=ProviderMetadata(provider="stub", retrieved_at=datetime.now(timezone.utc)),
            score=90,
            mx_records=True,
        )


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


async def _make_company_and_contact(db_session, workspace_id, *, with_email=False, with_company=True):
    company = None
    if with_company:
        company = Company(workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", domain="acmedental.example")
        db_session.add(company)
        await db_session.flush()

    contact = Contact(
        workspace_id=uuid.UUID(workspace_id),
        company_id=company.id if company else None,
        first_name="Jordan",
        last_name="Alvarez",
        full_name="Jordan Alvarez",
        email="jordan@acmedental.example" if with_email else None,
    )
    db_session.add(contact)
    await db_session.commit()
    return contact


async def test_find_email_persists_result(client, db_session, unique_email, monkeypatch):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.email_discovery_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubEmailFinder(),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/find-email",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email_found"] is True
    assert body["confidence"] == "found"
    assert body["contact"]["email"] == "jordan@acmedental.example"


async def test_find_email_skips_provider_call_when_email_already_present(
    client, db_session, unique_email
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=True)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/find-email",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["email_found"] is False


async def test_find_email_requires_company_domain(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_company=False)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/find-email",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 400


async def test_find_email_reports_missing_credentials(client, db_session, unique_email):
    """When every enabled email-finder provider lacks credentials, nothing
    was actually attempted — that's a config problem (503), not a genuine
    empty search result."""
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/find-email",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 503
    assert "hunter" in response.json()["detail"]


async def test_verify_email_persists_and_returns_verification(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=True)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_VERIFIER, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.email_verification_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubEmailVerifier(),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/verify",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "valid"
    assert body["verification_score"] == 90

    latest_response = await client.get(
        f"/api/v1/leads/{contact.id}/verification",
        params={"workspace_id": workspace_id},
        headers=headers,
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == body["id"]


async def test_verify_email_requires_existing_email(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=False)

    db_session.add(
        ProviderConfig(provider="hunter", category=ProviderCategory.EMAIL_VERIFIER, enabled=True, priority=1)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/leads/{contact.id}/verify",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 400


async def test_get_verification_404_when_none_exists(client, db_session, unique_email):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=True)

    response = await client.get(
        f"/api/v1/leads/{contact.id}/verification",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 404
