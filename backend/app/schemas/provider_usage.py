import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.providers.base import ProviderCategory


class ProviderUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    category: ProviderCategory
    operation: str
    workspace_id: uuid.UUID | None
    success: bool
    error: str | None
    duration_ms: float
    records_returned: int | None
    estimated_cost: float | None
    occurred_at: datetime


class ProviderHealthRead(BaseModel):
    provider: str
    category: ProviderCategory
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration_ms: float
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error: str | None
    calls_this_month: int
    monthly_free_quota: int | None
    quota_remaining: int | None
