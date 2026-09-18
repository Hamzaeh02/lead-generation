import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp_profile import ICPProfile


class ICPProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> ICPProfile:
        profile = ICPProfile(**fields)
        self.session.add(profile)
        return profile

    async def get_by_id(self, workspace_id: uuid.UUID, profile_id: uuid.UUID) -> ICPProfile | None:
        result = await self.session.execute(
            select(ICPProfile).where(
                ICPProfile.id == profile_id, ICPProfile.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[ICPProfile]:
        result = await self.session.execute(
            select(ICPProfile)
            .where(ICPProfile.workspace_id == workspace_id)
            .order_by(ICPProfile.created_at.desc())
        )
        return list(result.scalars().all())
