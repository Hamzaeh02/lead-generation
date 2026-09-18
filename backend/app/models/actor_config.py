from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.providers.base import ProviderCategory


class ActorConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configured Apify Actor. Apify is not one fixed integration — any
    number of actors can be registered here, each scoped to a discovery
    category, so the platform never hard-codes which actor to run."""

    __tablename__ = "actor_configs"

    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ProviderCategory] = mapped_column(
        Enum(ProviderCategory, name="provider_category", values_callable=str_enum_values), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Documents the actor's expected input keys/defaults; merged into the
    # run input built from DiscoveryCriteria. Not enforced/validated — actor
    # input schemas vary too much to generalize.
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
