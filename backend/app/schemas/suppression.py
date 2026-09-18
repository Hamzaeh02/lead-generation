import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.email_event import EmailEventType
from app.models.suppression import SuppressionReason


class SuppressionCreate(BaseModel):
    email: str
    reason: SuppressionReason = SuppressionReason.MANUAL


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    reason: SuppressionReason
    campaign_id: uuid.UUID | None
    created_at: datetime


class EmailEventWebhook(BaseModel):
    """Generic inbound event payload — real ESPs (SES, SendGrid, Postmark,
    Mailgun) each have their own webhook shape; this is the normalized
    form a thin per-provider adapter would map into (adapters are not
    built yet — this endpoint accepts the normalized shape directly)."""

    workspace_id: uuid.UUID
    contact_email: str
    event_type: EmailEventType
    campaign_recipient_id: uuid.UUID | None = None
    raw_payload: dict = {}


class EmailEventWebhookResponse(BaseModel):
    recorded: bool
    campaign_recipient_id: uuid.UUID | None
    suppressed: bool
