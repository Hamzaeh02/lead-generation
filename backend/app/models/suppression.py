from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class SuppressionReason(StrEnum):
    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    MANUAL = "manual"
    COMPLAINT = "complaint"
    REPLY_OPT_OUT = "reply_opt_out"


class Suppression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-level do-not-contact list. Checked before every send —
    an email on this list is never sent to again for that workspace,
    regardless of which campaign or contact record triggers the attempt."""

    __tablename__ = "suppressions"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_suppression_workspace_email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason, name="suppression_reason", values_callable=str_enum_values), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
