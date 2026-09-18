import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_event import EmailEvent


class EmailEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> EmailEvent:
        event = EmailEvent(**fields)
        self.session.add(event)
        return event

    async def list_for_recipient(self, campaign_recipient_id: uuid.UUID) -> list[EmailEvent]:
        result = await self.session.execute(
            select(EmailEvent)
            .where(EmailEvent.campaign_recipient_id == campaign_recipient_id)
            .order_by(EmailEvent.occurred_at.desc())
        )
        return list(result.scalars().all())
