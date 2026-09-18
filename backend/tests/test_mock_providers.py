"""End-to-end check that the provider interface -> normalization -> dedup ->
provenance pipeline works using the dev-only mock providers. No network
calls; MockCompanyDiscoveryProvider/MockPersonDiscoveryProvider return
clearly-labeled fixture data (see their module docstrings)."""
import uuid

import pytest

from app.providers.base import DiscoveryCriteria
from app.providers.lead_sources.mock_provider import MockCompanyDiscoveryProvider
from app.providers.people_sources.mock_provider import MockPersonDiscoveryProvider
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.services.company_resolver import CompanyEntityResolver
from app.services.contact_resolver import PersonEntityResolver

pytestmark = pytest.mark.asyncio


async def test_mock_company_provider_results_flow_through_resolver(db_session):
    provider = MockCompanyDiscoveryProvider()
    resolver = CompanyEntityResolver(CompanyRepository(db_session))
    workspace_id = uuid.uuid4()

    companies = await provider.discover_companies(
        DiscoveryCriteria(industry="dental", state="FL", limit=10)
    )
    assert len(companies) == 1
    assert companies[0].metadata.raw_reference["environment"] == "development"

    resolution = await resolver.resolve(workspace_id=workspace_id, candidate=companies[0])
    assert resolution.created is True
    assert resolution.company.name == "Acme Dental Group"
    assert resolution.company.field_provenance["name"]["provider"] == "mock_company_discovery"


async def test_mock_person_provider_decision_makers_flow_through_resolver(db_session):
    provider = MockPersonDiscoveryProvider()
    resolver = PersonEntityResolver(ContactRepository(db_session))
    workspace_id = uuid.uuid4()

    people = await provider.discover_decision_makers("acmedental.example", ["Owner"])
    assert len(people) == 1

    resolution = await resolver.resolve(
        workspace_id=workspace_id, candidate=people[0], company_id=None
    )
    assert resolution.created is True
    assert resolution.contact.job_title == "Owner"
