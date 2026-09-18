import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_verification import EmailVerification


class EmailVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> EmailVerification:
        verification = EmailVerification(**fields)
        self.session.add(verification)
        return verification

    async def get_latest_for_contact(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> EmailVerification | None:
        result = await self.session.execute(
            select(EmailVerification)
            .where(
                EmailVerification.workspace_id == workspace_id,
                EmailVerification.contact_id == contact_id,
            )
            .order_by(EmailVerification.verified_at.desc())
            .limit(1)
        )
        return result.scalars().first()
