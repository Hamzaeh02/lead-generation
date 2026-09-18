"""Suppression checks (section 44). This is the single choke point every
send must pass through — never send to a suppressed email, no exceptions,
regardless of which campaign or code path is attempting it."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suppression import Suppression, SuppressionReason
from app.repositories.suppression_repository import SuppressionRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SuppressionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SuppressionRepository(session)

    async def is_suppressed(self, workspace_id: uuid.UUID, email: str) -> bool:
        if not email:
            return False
        return await self.repo.find(workspace_id, email) is not None

    async def suppress(
        self,
        *,
        workspace_id: uuid.UUID,
        email: str,
        reason: SuppressionReason,
        campaign_id: uuid.UUID | None = None,
    ) -> Suppression:
        normalized_email = email.strip().lower()
        existing = await self.repo.find(workspace_id, normalized_email)
        if existing is not None:
            return existing

        suppression = self.repo.create(
            workspace_id=workspace_id,
            email=normalized_email,
            reason=reason,
            campaign_id=campaign_id,
        )
        logger.info(
            "email_suppressed", workspace_id=str(workspace_id), reason=str(reason), email=normalized_email
        )
        return suppression
