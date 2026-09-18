from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.providers.base import ProviderCategory


class ProviderUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per provider call. Immutable log — the basis for cost
    tracking (section 50) and provider health (section 53), both computed
    on read rather than maintained as separately-mutated aggregate state."""

    __tablename__ = "provider_usage"

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[ProviderCategory] = mapped_column(
        Enum(ProviderCategory, name="provider_category", values_callable=str_enum_values), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    records_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
