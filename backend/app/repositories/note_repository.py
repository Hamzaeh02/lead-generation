import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


class NoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> Note:
        note = Note(**fields)
        self.session.add(note)
        return note

    async def list_for_contact(self, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> list[Note]:
        result = await self.session.execute(
            select(Note)
            .where(Note.workspace_id == workspace_id, Note.contact_id == contact_id)
            .order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())
