"""Phase 6: waterfall fallback across enabled providers + cost tracking/health."""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.company import Company
from app.models.contact import Contact
from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory, ProviderMetadata, ProviderUnavailableError
from app.providers.email_finders.base import EmailCandidate, EmailConfidence, EmailFinderProvider
from app.providers.email_verifiers.base import (
    EmailVerifierProvider,
    VerificationResult,
    VerificationStatus,
)

pytestmark = pytest.mark.asyncio


class _FailingFinder(EmailFinderProvider):
    name = "failing"
    category = ProviderCategory.EMAIL_FINDER

    async def find_email(self, *, first_name, last_name, full_name, company_domain):
        raise ProviderUnavailableError("failing: simulated outage")


class _SucceedingFinder(EmailFinderProvider):
    name = "succeeding"
    category = ProviderCategory.EMAIL_FINDER

    async def find_email(self, *, first_name, last_name, full_name, company_domain):
        return EmailCandidate(
            email=f"jordan@{company_domain}",
            confidence=EmailConfidence.FOUND,
            metadata=ProviderMetadata(provider="succeeding", retrieved_at=datetime.now(timezone.utc)),
        )


class _FailingVerifier(EmailVerifierProvider):
    name = "failing"
    category = ProviderCategory.EMAIL_VERIFIER

    async def verify(self, email):
        raise ProviderUnavailableError("failing: simulated outage")


class _SucceedingVerifier(EmailVerifierProvider):
    name = "succeeding"
    category = ProviderCategory.EMAIL_VERIFIER

    async def verify(self, email):
        return VerificationResult(
            status=VerificationStatus.VALID,
            metadata=ProviderMetadata(provider="succeeding", retrieved_at=datetime.now(timezone.utc)),
            score=88,
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


async def _make_company_and_contact(db_session, workspace_id, *, with_email=False):
    company = Company(
        workspace_id=uuid.UUID(workspace_id), name="Acme Dental Group", domain="acmedental.example"
    )
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        workspace_id=uuid.UUID(workspace_id),
        company_id=company.id,
        first_name="Jordan",
        last_name="Alvarez",
        full_name="Jordan Alvarez",
        email="jordan@acmedental.example" if with_email else None,
    )
    db_session.add(contact)
    await db_session.commit()
    return contact


async def test_find_email_falls_back_to_second_provider_after_first_fails(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id)

    db_session.add(
        ProviderConfig(provider="failing", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=1)
    )
    db_session.add(
        ProviderConfig(provider="succeeding", category=ProviderCategory.EMAIL_FINDER, enabled=True, priority=2)
    )
    await db_session.commit()

    def fake_build(provider_name, category, settings):
        return {"failing": _FailingFinder(), "succeeding": _SucceedingFinder()}[provider_name]

    monkeypatch.setattr("app.services.email_discovery_service.provider_factory.build_provider", fake_build)

    response = await client.post(
        f"/api/v1/leads/{contact.id}/find-email",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email_found"] is True
    assert body["contact"]["email"] == "jordan@acmedental.example"

    usage_response = await client.get(
        "/api/v1/providers/usage", params={"category": "email_finder"}, headers=headers
    )
    usage_rows = usage_response.json()
    assert any(r["provider"] == "failing" and r["success"] is False for r in usage_rows)
    assert any(r["provider"] == "succeeding" and r["success"] is True for r in usage_rows)


async def test_verify_falls_back_to_second_provider_after_first_fails(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=True)

    db_session.add(
        ProviderConfig(provider="failing", category=ProviderCategory.EMAIL_VERIFIER, enabled=True, priority=1)
    )
    db_session.add(
        ProviderConfig(provider="succeeding", category=ProviderCategory.EMAIL_VERIFIER, enabled=True, priority=2)
    )
    await db_session.commit()

    def fake_build(provider_name, category, settings):
        return {"failing": _FailingVerifier(), "succeeding": _SucceedingVerifier()}[provider_name]

    monkeypatch.setattr("app.services.email_verification_service.provider_factory.build_provider", fake_build)

    response = await client.post(
        f"/api/v1/leads/{contact.id}/verify",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "succeeding"
    assert body["verification_status"] == "valid"


async def test_verify_returns_502_when_all_providers_fail_but_were_attempted(
    client, db_session, unique_email, monkeypatch
):
    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    contact = await _make_company_and_contact(db_session, workspace_id, with_email=True)

    db_session.add(
        ProviderConfig(provider="failing", category=ProviderCategory.EMAIL_VERIFIER, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.email_verification_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _FailingVerifier(),
    )

    response = await client.post(
        f"/api/v1/leads/{contact.id}/verify",
        params={"workspace_id": workspace_id},
        headers=headers,
    )

    assert response.status_code == 502


async def test_provider_usage_recorded_for_search_execute(client, db_session, unique_email, monkeypatch):
    from app.providers.base import DiscoveryCriteria, NormalizedCompany
    from app.providers.lead_sources.base import CompanyDiscoveryProvider

    class _StubProvider(CompanyDiscoveryProvider):
        name = "stub"
        category = ProviderCategory.COMPANY_DISCOVERY

        async def discover_companies(self, criteria: DiscoveryCriteria) -> list[NormalizedCompany]:
            return [
                NormalizedCompany(
                    metadata=ProviderMetadata(provider="stub"), name="Acme Dental Group", domain="acmedental.example"
                )
            ]

    headers, workspace_id = await _register_and_get_workspace(client, unique_email)
    db_session.add(
        ProviderConfig(provider="stub", category=ProviderCategory.COMPANY_DISCOVERY, enabled=True, priority=1)
    )
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.search_service.provider_factory.build_provider",
        lambda provider_name, category, settings: _StubProvider(),
    )

    await client.post(
        "/api/v1/search/execute",
        json={
            "workspace_id": workspace_id,
            "provider": "stub",
            "category": "company_discovery",
            "criteria": {},
        },
        headers=headers,
    )

    health_response = await client.get("/api/v1/providers/health", headers=headers)
    health = {(row["provider"], row["category"]): row for row in health_response.json()}
    entry = health[("stub", "company_discovery")]
    assert entry["total_calls"] == 1
    assert entry["success_count"] == 1
    assert entry["success_rate"] == 1.0
    assert entry["last_success_at"] is not None


async def test_provider_health_and_usage_require_authentication(client):
    assert (await client.get("/api/v1/providers/usage")).status_code == 401
    assert (await client.get("/api/v1/providers/health")).status_code == 401
