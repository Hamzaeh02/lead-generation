import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_recipient import CampaignRecipient, RecipientStatus
from app.models.email_event import EmailEvent, EmailEventType


class CampaignRecipientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> CampaignRecipient:
        recipient = CampaignRecipient(**fields)
        self.session.add(recipient)
        return recipient

    async def find(self, campaign_id: uuid.UUID, contact_id: uuid.UUID) -> CampaignRecipient | None:
        result = await self.session.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.contact_id == contact_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_due(
        self, campaign_id: uuid.UUID, *, now: datetime, limit: int
    ) -> list[CampaignRecipient]:
        result = await self.session.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.PENDING,
                CampaignRecipient.next_send_at <= now,
            )
            .order_by(CampaignRecipient.next_send_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_for_campaign(self, campaign_id: uuid.UUID) -> list[CampaignRecipient]:
        result = await self.session.execute(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id)
        )
        return list(result.scalars().all())

    async def count_sent_today(self, campaign_id: uuid.UUID, *, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(EmailEvent)
            .join(CampaignRecipient, EmailEvent.campaign_recipient_id == CampaignRecipient.id)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                EmailEvent.event_type == EmailEventType.SENT,
                EmailEvent.occurred_at >= since,
            )
        )
        return result.scalar_one()

    async def find_by_contact_across_workspace(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> list[CampaignRecipient]:
        result = await self.session.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.workspace_id == workspace_id,
                CampaignRecipient.contact_id == contact_id,
            )
        )
        return list(result.scalars().all())
