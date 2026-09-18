import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> Task:
        task = Task(**fields)
        self.session.add(task)
        return task

    async def get_by_id(self, workspace_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def list_for_contact(self, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.workspace_id == workspace_id, Task.contact_id == contact_id)
            .order_by(Task.completed, Task.due_at.is_(None), Task.due_at)
        )
        return list(result.scalars().all())
