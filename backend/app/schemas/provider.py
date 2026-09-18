import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import ProviderCategory


class ProviderConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    category: ProviderCategory
    enabled: bool
    priority: int
    monthly_free_quota: int | None
    config: dict[str, Any]


class ProviderConfigUpdate(BaseModel):
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1)
    monthly_free_quota: int | None = None
