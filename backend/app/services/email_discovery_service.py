"""EmailDiscoveryOrchestrator: waterfall across every enabled email_finder
provider, in registry priority order.

Never calls a provider if the contact already has an email
(minimum-necessary-calls, per the platform's cost-awareness principle),
and never fabricates a value — exhausting the waterfall without a match is
a normal, non-error outcome. Every attempt (including providers skipped
for missing credentials, and failures) is logged via ProviderUsageRecorder
for cost tracking and provider health (Phase 6). The waterfall stops at
the first provider that returns a match; a provider that errors or finds
nothing is not fatal — the next one in priority order is tried.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.contact import Contact
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.email_finders.base import EmailCandidate
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmailDiscoveryService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.contacts = ContactRepository(session)
        self.companies = CompanyRepository(session)
        self.provider_configs = ProviderConfigRepository(session)

    async def find_email(
        self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> tuple[Contact, EmailCandidate | None]:
        contact = await self.contacts.get_by_id(workspace_id, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
        if contact.email:
            return contact, None

        domain = await self._resolve_company_domain(workspace_id, contact)
        if not domain:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Contact has no associated company domain to search against",
            )

        registry_entries = await self.provider_configs.list_enabled_for_category(
            ProviderCategory.EMAIL_FINDER
        )
        if not registry_entries:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "No email-finder provider is enabled in the registry"
            )

        missing_credentials: list[str] = []
        for registry_entry in registry_entries:
            provider = provider_factory.build_provider(
                registry_entry.provider, ProviderCategory.EMAIL_FINDER, self.settings
            )
            if provider is None:
                missing_credentials.append(registry_entry.provider)
                continue

            found: EmailCandidate | None = None
            try:
                # The try/except deliberately wraps the `async with`, not the
                # other way around: ProviderUsageRecorder.__aexit__ needs to
                # see the real exception to log success=False. Catching it
                # inside the block first would hide the failure from the
                # usage log — exactly the bug this comment is here to
                # prevent from being reintroduced.
                async with ProviderUsageRecorder(
                    self.session,
                    provider=registry_entry.provider,
                    category=ProviderCategory.EMAIL_FINDER,
                    operation="find_email",
                    workspace_id=workspace_id,
                ) as usage:
                    found = await provider.find_email(
                        first_name=contact.first_name,
                        last_name=contact.last_name,
                        full_name=contact.full_name,
                        company_domain=domain,
                    )
                    usage.records_returned = 1 if found else 0
            except ProviderUnavailableError as exc:
                logger.warning(
                    "email_discovery_provider_unavailable",
                    provider=registry_entry.provider,
                    error=str(exc),
                )
                continue  # not fatal — fall through to the next provider

            if found is not None:
                return await self._persist_email(contact, found)

        if len(missing_credentials) == len(registry_entries):
            # Every enabled provider was skipped for missing credentials —
            # nothing was actually attempted, so this is a config problem,
            # not a genuine "searched and found nothing" outcome.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No enabled email-finder provider has credentials configured "
                f"(missing: {', '.join(missing_credentials)}).",
            )
        return contact, None

    async def _persist_email(
        self, contact: Contact, found: EmailCandidate
    ) -> tuple[Contact, EmailCandidate]:
        contact.email = found.email
        provenance = dict(contact.field_provenance)
        provenance["email"] = {
            "provider": found.metadata.provider,
            "retrieved_at": found.metadata.retrieved_at.isoformat(),
            "confidence": found.confidence.value,
        }
        contact.field_provenance = provenance

        self.contacts.add_source(
            contact=contact,
            provider=found.metadata.provider,
            external_id=found.metadata.external_id,
            source_url=found.metadata.source_url,
            source_type=found.metadata.source_type,
            raw_reference=found.metadata.raw_reference,
        )
        await self.session.commit()
        # `last_seen`/`updated_at` use onupdate=func.now(); after commit their
        # true value only exists server-side, so the in-memory object is
        # expired for those columns. Refresh before returning it for
        # (sync) Pydantic serialization, which can't await a lazy reload.
        await self.session.refresh(contact)

        logger.info(
            "email_found", contact_id=str(contact.id), provider=found.metadata.provider,
            confidence=found.confidence.value,
        )
        return contact, found

    async def _resolve_company_domain(
        self, workspace_id: uuid.UUID, contact: Contact
    ) -> str | None:
        if contact.company_id is None:
            return None
        company = await self.companies.get_by_id(workspace_id, contact.company_id)
        return company.domain if company else None
