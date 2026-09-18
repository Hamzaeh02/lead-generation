"""EmailVerificationOrchestrator: waterfall across enabled email_verifier
providers, in registry priority order.

Stops at the first provider that successfully returns a result (any
status — valid/invalid/risky/unknown are all legitimate outcomes); only a
provider error or missing credentials triggers falling through to the
next one. Multi-provider confidence blending (section 27 — e.g. two
providers agreeing pushes confidence to "high") is deferred until a
second real verifier exists; blending logic against only Hunter would be
untested and speculative. Every attempt is logged via
ProviderUsageRecorder for cost tracking and provider health.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.contact import LeadStatus
from app.models.email_verification import EmailVerification
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.email_verifiers.base import VerificationStatus
from app.repositories.contact_repository import ContactRepository
from app.repositories.email_verification_repository import EmailVerificationRepository
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.services.provider_usage_tracker import ProviderUsageRecorder
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmailVerificationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.contacts = ContactRepository(session)
        self.provider_configs = ProviderConfigRepository(session)
        self.verifications = EmailVerificationRepository(session)

    async def verify(
        self, *, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> EmailVerification:
        contact = await self.contacts.get_by_id(workspace_id, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
        if not contact.email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Contact has no email to verify")

        registry_entries = await self.provider_configs.list_enabled_for_category(
            ProviderCategory.EMAIL_VERIFIER
        )
        if not registry_entries:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "No email-verifier provider is enabled in the registry"
            )

        missing_credentials: list[str] = []
        last_error: str | None = None
        for registry_entry in registry_entries:
            provider = provider_factory.build_provider(
                registry_entry.provider, ProviderCategory.EMAIL_VERIFIER, self.settings
            )
            if provider is None:
                missing_credentials.append(registry_entry.provider)
                continue

            try:
                # See the comment in EmailDiscoveryService.find_email: the
                # try/except must wrap the `async with`, not sit inside it,
                # or ProviderUsageRecorder never sees the real exception.
                async with ProviderUsageRecorder(
                    self.session,
                    provider=registry_entry.provider,
                    category=ProviderCategory.EMAIL_VERIFIER,
                    operation="verify",
                    workspace_id=workspace_id,
                ) as usage:
                    result = await provider.verify(contact.email)
                    usage.records_returned = 1
            except ProviderUnavailableError as exc:
                logger.warning(
                    "email_verification_provider_unavailable",
                    provider=registry_entry.provider,
                    error=str(exc),
                )
                last_error = str(exc)
                continue  # not fatal — fall through to the next provider

            verification = self.verifications.create(
                workspace_id=workspace_id,
                contact_id=contact.id,
                email=contact.email,
                provider=result.metadata.provider,
                verification_status=result.status,
                verification_score=result.score,
                mx_records=result.mx_records,
                smtp_check=result.smtp_check,
                accept_all=result.accept_all,
                disposable=result.disposable,
                free_provider=result.free_provider,
                role_account=result.role_account,
                raw_response=result.metadata.raw_reference,
                verified_at=result.metadata.retrieved_at,
            )
            # CRM pipeline: a valid verification is meaningful progress for
            # a still-New lead. Never downgrades a further-along status.
            if result.status == VerificationStatus.VALID and contact.status == LeadStatus.NEW:
                contact.status = LeadStatus.VERIFIED

            await self.session.commit()
            await self.session.refresh(verification)

            logger.info(
                "email_verified", contact_id=str(contact.id), provider=result.metadata.provider,
                status=str(result.status),
            )
            return verification

        if len(missing_credentials) == len(registry_entries):
            # Every enabled provider was skipped for missing credentials —
            # nothing was actually attempted, so this is a config problem.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No enabled email-verifier provider has credentials configured "
                f"(missing: {', '.join(missing_credentials)}).",
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"All enabled email-verifier providers failed. Last error: {last_error}",
        )
