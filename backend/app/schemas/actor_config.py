import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import ProviderCategory


class ActorConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_name: str
    actor_id: str
    category: ProviderCategory
    enabled: bool
    priority: int
    estimated_cost: float | None
    input_schema: dict[str, Any]


class ActorConfigCreate(BaseModel):
    actor_name: str
    actor_id: str
    category: ProviderCategory
    enabled: bool = False
    priority: int = 100
    estimated_cost: float | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ActorConfigUpdate(BaseModel):
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1)
    estimated_cost: float | None = None
    input_schema: dict[str, Any] | None = None
