from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.providers.base import ProviderCategory


class ProviderConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provider registry row: one (provider, category) pair.

    Platform-level configuration, not workspace-owned data — administrators
    enable/disable providers and set priority/limits here. Credentials
    themselves are never stored in this table; they come from environment
    variables (see .env.example) and are referenced only by name if needed.
    """

    __tablename__ = "provider_configs"
    __table_args__ = (UniqueConstraint("provider", "category", name="uq_provider_category"),)

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[ProviderCategory] = mapped_column(
        Enum(ProviderCategory, name="provider_category", values_callable=str_enum_values), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    # How many calls/month this provider's free tier allows, if any is known
    # (e.g. Hunter: 25 finder + 50 verifier; SerpApi: 250 searches). Null
    # means "no known free-tier cap" — either genuinely unlimited (OSM) or
    # simply not tracked. Purely informational: nothing blocks a call past
    # this number, but GET /api/v1/providers/health surfaces how close a
    # provider is to its free quota this month.
    monthly_free_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Non-secret configuration only (e.g. actor_id, request timeout, notes).
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
