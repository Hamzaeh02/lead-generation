from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values
from app.providers.email_verifiers.base import VerificationStatus


class EmailVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One verification attempt for one email, from one provider. A contact
    can accumulate several of these over time (re-verification, multiple
    providers) — the most recent is the contact's current status."""

    __tablename__ = "email_verifications"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", values_callable=str_enum_values), nullable=False
    )
    verification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mx_records: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    smtp_check: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accept_all: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disposable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    free_provider: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    role_account: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
