from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ICPProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved Ideal Customer Profile definition. Scoring (ICPScoreService)
    compares a Company/its Contacts against these criteria — every field is
    optional, so an unset criterion simply doesn't contribute to the score
    rather than penalizing or fabricating a match."""

    __tablename__ = "icp_profiles"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_count_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_titles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Optional per-criterion weight overrides (see ICPScoreService.DEFAULT_WEIGHTS).
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
