from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values


class EmailEventType(StrEnum):
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    COMPLAINED = "complained"
    OUT_OF_OFFICE = "out_of_office"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ReplySentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class EmailEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable log of everything that happens to a sent email — the raw
    webhook/IMAP payload is always kept in `raw_payload` for audit, even
    though we also parse it into a typed `event_type`."""

    __tablename__ = "email_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    campaign_recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaign_recipients.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[EmailEventType] = mapped_column(
        Enum(EmailEventType, name="email_event_type", values_callable=str_enum_values), nullable=False
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reply_sentiment: Mapped[ReplySentiment | None] = mapped_column(
        Enum(ReplySentiment, name="reply_sentiment", values_callable=str_enum_values), nullable=True
    )
