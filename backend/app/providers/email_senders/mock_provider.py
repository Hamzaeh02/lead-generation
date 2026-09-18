"""Development/test-only email sender. Never actually sends — logs and
returns SENT. Must never be selected in production (nothing in
provider_factory wires it up; it exists purely for local dev/testing so
campaigns can be exercised without real SMTP credentials or hitting a
real inbox)."""
from __future__ import annotations

from app.providers.base import ProviderCategory
from app.providers.email_senders.base import EmailSenderProvider, OutboundEmail, SendResult, SendStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MockEmailSenderProvider(EmailSenderProvider):
    name = "mock_email_sender"
    category = ProviderCategory.EMAIL_SENDER

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[OutboundEmail] = []

    async def send(self, message: OutboundEmail) -> SendResult:
        self.sent.append(message)
        logger.info(
            "mock_email_sent",
            environment="development",
            to=message.to_email,
            subject=message.subject,
        )
        return SendResult(status=SendStatus.SENT, provider_message_id="mock-message-id")
