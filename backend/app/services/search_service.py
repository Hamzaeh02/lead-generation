"""Ties together: provider registry check -> provider instantiation ->
discovery call -> normalization/dedup (via the Phase 2 resolvers) -> persist.

This is a single explicit provider call (the caller picks exactly one
enabled provider and category) — not the cross-category named waterfall
strategies described in section 51 ("B2B: Apollo → PDL → Hunter → ...").
Same-category multi-provider waterfall fallback exists for email discovery/
verification (see EmailDiscoveryService/EmailVerificationService); search
keeps explicit provider selection since the NL-search UI flow (section 60)
has the user choose providers as a distinct step. Every call is logged via
ProviderUsageRecorder for cost tracking and provider health (Phase 6).
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.company import Company
from app.models.contact import Contact
from app.providers.base import (
    DiscoveryCriteria,
    NormalizedCompany,
    NormalizedContact,
    ProviderCategory,
    ProviderUnavailableError,
)
from app.providers.lead_sources.apify_provider import (
    ApifyClient,
    ApifyCompanyDiscoveryProvider,
    ApifyLocalBusinessDiscoveryProvider,
)
from app.repositories.actor_config_repository import ActorConfigRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.company_resolver import CompanyEntityResolver
from app.services.contact_resolver import PersonEntityResolver
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DISCOVERY_CATEGORIES = {
    ProviderCategory.COMPANY_DISCOVERY,
    ProviderCategory.PERSON_DISCOVERY,
    ProviderCategory.LOCAL_BUSINESS_DISCOVERY,
}


class SearchService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.provider_configs = ProviderConfigRepository(session)
        self.actor_configs = ActorConfigRepository(session)
        self.company_resolver = CompanyEntityResolver(CompanyRepository(session))
        self.contact_resolver = PersonEntityResolver(ContactRepository(session))

    async def execute(
        self,
        *,
        workspace_id: uuid.UUID,
        provider_name: str,
        category: ProviderCategory,
        criteria: DiscoveryCriteria,
    ) -> dict:
        if category not in _DISCOVERY_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{category}' does not support discovery search",
            )

        registry_entry = await self.provider_configs.get_by_provider_and_category(
            provider_name, category
        )
        if registry_entry is None or not registry_entry.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider_name}' is not enabled for category '{category}'. "
                    "An admin must enable it via PATCH /api/v1/providers/{id}."
                ),
            )

        if provider_name == "apify":
            provider = await self._build_apify_provider(category)
        else:
            provider = provider_factory.build_provider(provider_name, category, self.settings)
            if provider is None:
                env_var = provider_factory.required_env_var(provider_name, category)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Provider '{provider_name}' credentials not configured (set {env_var}).",
                )

        contacts_found: list[NormalizedContact] = []
        companies_found: list[NormalizedCompany] = []
        operation = {
            ProviderCategory.COMPANY_DISCOVERY: "discover_companies",
            ProviderCategory.LOCAL_BUSINESS_DISCOVERY: "discover_local_businesses",
            ProviderCategory.PERSON_DISCOVERY: "discover_people",
        }[category]

        async with ProviderUsageRecorder(
            self.session,
            provider=provider_name,
            category=category,
            operation=operation,
            workspace_id=workspace_id,
        ) as usage:
            try:
                if category == ProviderCategory.COMPANY_DISCOVERY:
                    companies_found = await provider.discover_companies(criteria)
                elif category == ProviderCategory.LOCAL_BUSINESS_DISCOVERY:
                    companies_found = await provider.discover_local_businesses(criteria)
                else:  # PERSON_DISCOVERY
                    contacts_found = await provider.discover_people(criteria)
            except ProviderUnavailableError as exc:
                logger.warning("search_provider_unavailable", provider=provider_name, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Provider request failed: {exc}",
                ) from exc
            finally:
                usage.records_returned = len(companies_found) + len(contacts_found)

        companies_created = companies_matched = 0
        touched_companies: dict[uuid.UUID, Company] = {}

        for candidate in companies_found:
            resolution = await self.company_resolver.resolve(
                workspace_id=workspace_id, candidate=candidate
            )
            touched_companies[resolution.company.id] = resolution.company
            if resolution.created:
                companies_created += 1
            else:
                companies_matched += 1

        contacts_created = contacts_matched = 0
        touched_contacts: dict[uuid.UUID, Contact] = {}

        for contact_candidate in contacts_found:
            company_id = await self._resolve_company_for_contact(workspace_id, contact_candidate)
            resolution = await self.contact_resolver.resolve(
                workspace_id=workspace_id, candidate=contact_candidate, company_id=company_id
            )
            touched_contacts[resolution.contact.id] = resolution.contact
            if resolution.created:
                contacts_created += 1
            else:
                contacts_matched += 1

        await self.session.commit()
        # Matched (not newly-created) records were mutated in-place, and
        # onupdate=func.now() columns are expired after commit — refresh
        # before returning them for (sync) Pydantic serialization.
        for company in touched_companies.values():
            await self.session.refresh(company)
        if touched_contacts:
            # A plain refresh() only covers column attributes, not the
            # `company` relationship ContactRead.company_name reads — a
            # fresh eager-loaded re-query both re-hydrates expired columns
            # and loads `company` in one pass, avoiding a MissingGreenlet
            # from an unloaded relationship touched during serialization.
            reloaded = await self.session.execute(
                select(Contact)
                .where(Contact.id.in_(touched_contacts.keys()))
                .options(selectinload(Contact.company))
            )
            touched_contacts = {c.id: c for c in reloaded.scalars().all()}

        logger.info(
            "search_executed",
            provider=provider_name,
            category=str(category),
            companies_created=companies_created,
            companies_matched=companies_matched,
            contacts_created=contacts_created,
            contacts_matched=contacts_matched,
        )

        return {
            "companies_created": companies_created,
            "companies_matched": companies_matched,
            "contacts_created": contacts_created,
            "contacts_matched": contacts_matched,
            "companies": list(touched_companies.values()),
            "contacts": list(touched_contacts.values()),
        }

    async def _build_apify_provider(self, category: ProviderCategory):
        if category not in (ProviderCategory.COMPANY_DISCOVERY, ProviderCategory.LOCAL_BUSINESS_DISCOVERY):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Apify does not support category '{category}' for discovery search",
            )

        actor_config = await self.actor_configs.get_best_for_category(category)
        if actor_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No enabled Apify actor configured for category '{category}'. "
                    "An admin must register one via POST /api/v1/apify/actors."
                ),
            )

        if not self.settings.APIFY_API_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Provider 'apify' credentials not configured (set APIFY_API_TOKEN).",
            )

        client = ApifyClient(api_token=self.settings.APIFY_API_TOKEN)
        if category == ProviderCategory.COMPANY_DISCOVERY:
            return ApifyCompanyDiscoveryProvider(actor_config=actor_config, client=client)
        return ApifyLocalBusinessDiscoveryProvider(actor_config=actor_config, client=client)

    async def _resolve_company_for_contact(
        self, workspace_id: uuid.UUID, contact: NormalizedContact
    ) -> uuid.UUID | None:
        """A person-search result often carries its employer's name/domain —
        resolve that into a Company too so the contact links to it, rather
        than leaving company_id null when we actually have the data."""
        if not contact.company_domain and not contact.company_name:
            return None

        company_candidate = NormalizedCompany(
            metadata=contact.metadata,
            name=contact.company_name,
            domain=contact.company_domain,
        )
        resolution = await self.company_resolver.resolve(
            workspace_id=workspace_id, candidate=company_candidate
        )
        return resolution.company.id
