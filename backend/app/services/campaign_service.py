"""Campaign lifecycle: creation, steps, enrollment, start/pause/resume."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.repositories.campaign_recipient_repository import CampaignRecipientRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_repository import ContactRepository


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.campaigns = CampaignRepository(session)
        self.recipients = CampaignRecipientRepository(session)
        self.contacts = ContactRepository(session)

    async def enroll_contacts(
        self, *, workspace_id: uuid.UUID, campaign_id: uuid.UUID, contact_ids: list[uuid.UUID]
    ) -> dict:
        campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
        if campaign is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        enrolled = already_enrolled = not_found = 0
        now = datetime.now(timezone.utc)

        for contact_id in contact_ids:
            contact = await self.contacts.get_by_id(workspace_id, contact_id)
            if contact is None:
                not_found += 1
                continue
            existing = await self.recipients.find(campaign_id, contact_id)
            if existing is not None:
                already_enrolled += 1
                continue
            self.recipients.create(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                contact_id=contact_id,
                next_send_at=now,
            )
            enrolled += 1

        await self.session.commit()
        return {"enrolled": enrolled, "already_enrolled": already_enrolled, "not_found": not_found}

    async def set_status(
        self, *, workspace_id: uuid.UUID, campaign_id: uuid.UUID, target: CampaignStatus
    ) -> Campaign:
        campaign = await self.campaigns.get_by_id(workspace_id, campaign_id)
        if campaign is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

        allowed_transitions: dict[CampaignStatus, set[CampaignStatus]] = {
            CampaignStatus.RUNNING: {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.PAUSED},
            CampaignStatus.PAUSED: {CampaignStatus.RUNNING},
            CampaignStatus.CANCELLED: {
                CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.RUNNING, CampaignStatus.PAUSED,
            },
        }
        if campaign.status not in allowed_transitions.get(target, set()):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot move campaign from '{campaign.status}' to '{target}'.",
            )

        if target == CampaignStatus.RUNNING and not campaign.steps:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Campaign has no steps — add at least one before starting."
            )

        campaign.status = target
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign
