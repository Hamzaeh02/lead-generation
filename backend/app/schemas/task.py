import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    title: str
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    completed: bool | None = None
    title: str | None = None
    due_at: datetime | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    title: str
    due_at: datetime | None
    completed: bool
    created_at: datetime
