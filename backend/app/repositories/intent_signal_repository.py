import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intent_signal import IntentSignal


class IntentSignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> IntentSignal:
        signal = IntentSignal(**fields)
        self.session.add(signal)
        return signal

    async def list_for_company(
        self, workspace_id: uuid.UUID, company_id: uuid.UUID
    ) -> list[IntentSignal]:
        result = await self.session.execute(
            select(IntentSignal)
            .where(
                IntentSignal.workspace_id == workspace_id, IntentSignal.company_id == company_id
            )
            .order_by(IntentSignal.detected_at.desc())
        )
        return list(result.scalars().all())
