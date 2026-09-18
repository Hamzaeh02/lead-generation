"""Email sending provider interface (SMTP, SES, SendGrid, Mailgun, Postmark, ...)."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.providers.base import BaseProvider


class SendStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    to_email: str
    from_email: str
    from_name: str | None
    subject: str
    html_body: str
    text_body: str | None = None
    reply_to: str | None = None
    unsubscribe_url: str | None = None


@dataclass(frozen=True, slots=True)
class SendResult:
    status: SendStatus
    provider_message_id: str | None = None
    error: str | None = None


class EmailSenderProvider(BaseProvider):
    @abstractmethod
    async def send(self, message: OutboundEmail) -> SendResult:
        raise NotImplementedError
