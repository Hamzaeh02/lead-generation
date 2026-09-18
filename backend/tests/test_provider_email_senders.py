from unittest.mock import MagicMock, patch

import pytest

from app.providers.base import ProviderUnavailableError
from app.providers.email_senders.base import OutboundEmail, SendStatus
from app.providers.email_senders.mock_provider import MockEmailSenderProvider
from app.providers.email_senders.smtp_provider import SMTPEmailSenderProvider

pytestmark = pytest.mark.asyncio


def _message() -> OutboundEmail:
    return OutboundEmail(
        to_email="jordan@acmedental.example",
        from_email="agency@example.com",
        from_name="Agency",
        subject="Hello",
        html_body="<p>Hi</p>",
        text_body="Hi",
        reply_to="reply@example.com",
        unsubscribe_url="/unsubscribe/tok",
    )


async def test_smtp_send_success():
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client

    with patch("app.providers.email_senders.smtp_provider.smtplib.SMTP", return_value=mock_client):
        provider = SMTPEmailSenderProvider(
            host="smtp.example.com", port=587, username="user", password="pass"
        )
        result = await provider.send(_message())

    assert result.status == SendStatus.SENT
    mock_client.starttls.assert_called_once()
    mock_client.login.assert_called_once_with("user", "pass")
    mock_client.sendmail.assert_called_once()


async def test_smtp_send_failure_returns_failed_status_not_exception():
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.login.side_effect = Exception("auth rejected")

    with patch("app.providers.email_senders.smtp_provider.smtplib.SMTP", return_value=mock_client):
        provider = SMTPEmailSenderProvider(
            host="smtp.example.com", port=587, username="user", password="wrong"
        )
        result = await provider.send(_message())

    assert result.status == SendStatus.FAILED
    assert "auth rejected" in result.error


async def test_smtp_missing_credentials_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        SMTPEmailSenderProvider(host="", port=587, username="user", password="pass")
    with pytest.raises(ProviderUnavailableError):
        SMTPEmailSenderProvider(host="smtp.example.com", port=587, username="", password="pass")


async def test_mock_provider_records_sent_messages_and_never_hits_network():
    provider = MockEmailSenderProvider()

    result = await provider.send(_message())

    assert result.status == SendStatus.SENT
    assert len(provider.sent) == 1
    assert provider.sent[0].to_email == "jordan@acmedental.example"
