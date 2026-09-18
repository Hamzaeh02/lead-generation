import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import LeadTag, Tag


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, *, workspace_id: uuid.UUID, name: str) -> Tag:
        tag = Tag(workspace_id=workspace_id, name=name)
        self.session.add(tag)
        return tag

    async def get_by_id(self, workspace_id: uuid.UUID, tag_id: uuid.UUID) -> Tag | None:
        result = await self.session.execute(
            select(Tag).where(Tag.id == tag_id, Tag.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, workspace_id: uuid.UUID, name: str) -> Tag | None:
        result = await self.session.execute(
            select(Tag).where(Tag.workspace_id == workspace_id, Tag.name == name)
        )
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[Tag]:
        result = await self.session.execute(
            select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name)
        )
        return list(result.scalars().all())

    async def list_for_contact(self, contact_id: uuid.UUID) -> list[Tag]:
        result = await self.session.execute(
            select(Tag).join(LeadTag, LeadTag.tag_id == Tag.id).where(LeadTag.contact_id == contact_id)
        )
        return list(result.scalars().all())

    async def is_tagged(self, contact_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(LeadTag).where(LeadTag.contact_id == contact_id, LeadTag.tag_id == tag_id)
        )
        return result.scalar_one_or_none() is not None

    def tag_contact(self, *, contact_id: uuid.UUID, tag_id: uuid.UUID) -> LeadTag:
        link = LeadTag(contact_id=contact_id, tag_id=tag_id)
        self.session.add(link)
        return link
