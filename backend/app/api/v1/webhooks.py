"""Inbound email-event ingestion (section 46) — bounce/reply/unsubscribe/
complaint detection. This accepts an already-normalized event shape;
provider-specific webhook adapters (SES, SendGrid, Postmark, Mailgun each
have their own payload format) are not built yet — see README. IMAP-based
reply detection (the spec's fallback path) is also not implemented; this
covers the webhook path only.

A `replied` event additionally gets a best-effort sentiment classification
(see reply_sentiment_service.py) when its `raw_payload` carries actual
reply text and an `ai`-category provider is enabled — this powers the
"positive replies" figure on the campaign report. No text or no provider
means it just stays unclassified, never guessed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.models.campaign_recipient import CampaignRecipient, RecipientStatus
from app.models.contact import LeadStatus
from app.models.email_event import EmailEventType
from app.models.suppression import SuppressionReason
from app.repositories.campaign_recipient_repository import CampaignRecipientRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.email_event_repository import EmailEventRepository
from app.schemas.suppression import EmailEventWebhook, EmailEventWebhookResponse
from app.services.reply_sentiment_service import classify_reply_sentiment, extract_reply_text
from app.services.suppression_service import SuppressionService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_SUPPRESSING_EVENTS = {
    EmailEventType.BOUNCED: SuppressionReason.BOUNCE,
    EmailEventType.UNSUBSCRIBED: SuppressionReason.UNSUBSCRIBE,
    EmailEventType.COMPLAINED: SuppressionReason.COMPLAINT,
}

_RECIPIENT_STATUS_FOR_EVENT = {
    EmailEventType.OPENED: RecipientStatus.OPENED,
    EmailEventType.CLICKED: RecipientStatus.CLICKED,
    EmailEventType.REPLIED: RecipientStatus.REPLIED,
    EmailEventType.BOUNCED: RecipientStatus.BOUNCED,
    EmailEventType.UNSUBSCRIBED: RecipientStatus.UNSUBSCRIBED,
}

# Contact-level CRM status (durable, cross-campaign) mirrors the
# recipient-level status for the same event types.
_LEAD_STATUS_FOR_EVENT = {
    EmailEventType.OPENED: LeadStatus.OPENED,
    EmailEventType.CLICKED: LeadStatus.CLICKED,
    EmailEventType.REPLIED: LeadStatus.REPLIED,
    EmailEventType.BOUNCED: LeadStatus.BOUNCED,
    EmailEventType.UNSUBSCRIBED: LeadStatus.UNSUBSCRIBED,
}


@router.post("/email-events", response_model=EmailEventWebhookResponse)
async def ingest_email_event(
    payload: EmailEventWebhook,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    recipient = None
    recipients_repo = CampaignRecipientRepository(session)

    if payload.campaign_recipient_id is not None:
        recipient = await session.get(CampaignRecipient, payload.campaign_recipient_id)
    else:
        contact = await ContactRepository(session).find_by_email(payload.workspace_id, payload.contact_email)
        if contact is not None:
            candidates = await recipients_repo.find_by_contact_across_workspace(
                payload.workspace_id, contact.id
            )
            recipient = candidates[-1] if candidates else None  # most recently created

    if recipient is None or recipient.workspace_id != payload.workspace_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No matching campaign recipient found for this event"
        )

    reply_sentiment = None
    if payload.event_type == EmailEventType.REPLIED:
        reply_text = extract_reply_text(payload.raw_payload)
        if reply_text:
            reply_sentiment = await classify_reply_sentiment(session, settings, reply_text)

    EmailEventRepository(session).create(
        workspace_id=payload.workspace_id,
        campaign_recipient_id=recipient.id,
        event_type=payload.event_type,
        raw_payload=payload.raw_payload,
        occurred_at=datetime.now(timezone.utc),
        reply_sentiment=reply_sentiment,
    )

    new_status = _RECIPIENT_STATUS_FOR_EVENT.get(payload.event_type)
    if new_status is not None:
        recipient.status = new_status

    lead_status = _LEAD_STATUS_FOR_EVENT.get(payload.event_type)
    if lead_status is not None:
        contact = await ContactRepository(session).get_by_id(payload.workspace_id, recipient.contact_id)
        if contact is not None:
            contact.status = lead_status

    suppressed = False
    suppression_reason = _SUPPRESSING_EVENTS.get(payload.event_type)
    if suppression_reason is not None:
        await SuppressionService(session).suppress(
            workspace_id=payload.workspace_id,
            email=payload.contact_email,
            reason=suppression_reason,
        )
        suppressed = True

    await session.commit()

    return EmailEventWebhookResponse(
        recorded=True, campaign_recipient_id=recipient.id, suppressed=suppressed
    )
