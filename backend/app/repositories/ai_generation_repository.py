import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generation import AIGeneration


class AIGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> AIGeneration:
        generation = AIGeneration(**fields)
        self.session.add(generation)
        return generation

    async def list_for_contact(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> list[AIGeneration]:
        result = await self.session.execute(
            select(AIGeneration)
            .where(
                AIGeneration.workspace_id == workspace_id, AIGeneration.contact_id == contact_id
            )
            .order_by(AIGeneration.generated_at.desc())
        )
        return list(result.scalars().all())
