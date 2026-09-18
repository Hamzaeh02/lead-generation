import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suppression import Suppression


class SuppressionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> Suppression:
        suppression = Suppression(**fields)
        self.session.add(suppression)
        return suppression

    async def find(self, workspace_id: uuid.UUID, email: str) -> Suppression | None:
        result = await self.session.execute(
            select(Suppression).where(
                Suppression.workspace_id == workspace_id, Suppression.email == email.strip().lower()
            )
        )
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[Suppression]:
        result = await self.session.execute(
            select(Suppression)
            .where(Suppression.workspace_id == workspace_id)
            .order_by(Suppression.created_at.desc())
        )
        return list(result.scalars().all())
