"""SMTP email sending — the generic fallback sender (section 42), not tied
to any one vendor. Uses the Python standard library's `smtplib` (no extra
dependency) wrapped in `asyncio.to_thread` since smtplib is synchronous.

This sends real email when configured with real SMTP credentials — there
is no way to test it against a live mail server in this environment, so
tests exercise it against a stub SMTP class instead of a real socket.
Requires SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.email_senders.base import EmailSenderProvider, OutboundEmail, SendResult, SendStatus


class SMTPEmailSenderProvider(EmailSenderProvider):
    name = "smtp"
    category = ProviderCategory.EMAIL_SENDER

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        super().__init__()
        if not host or not username or not password:
            raise ProviderUnavailableError(
                "smtp: SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD are not fully configured"
            )
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls

    async def send(self, message: OutboundEmail) -> SendResult:
        try:
            return await asyncio.to_thread(self._send_sync, message)
        except ProviderUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 — any smtplib failure becomes a SendResult
            return SendResult(status=SendStatus.FAILED, error=str(exc))

    def _send_sync(self, message: OutboundEmail) -> SendResult:
        mime_message = MIMEMultipart("alternative")
        mime_message["Subject"] = message.subject
        mime_message["From"] = (
            f"{message.from_name} <{message.from_email}>" if message.from_name else message.from_email
        )
        mime_message["To"] = message.to_email
        if message.reply_to:
            mime_message["Reply-To"] = message.reply_to

        if message.text_body:
            mime_message.attach(MIMEText(message.text_body, "plain"))
        mime_message.attach(MIMEText(message.html_body, "html"))

        with smtplib.SMTP(self._host, self._port, timeout=15) as client:
            if self._use_tls:
                client.starttls()
            client.login(self._username, self._password)
            client.sendmail(message.from_email, [message.to_email], mime_message.as_string())

        return SendResult(status=SendStatus.SENT)
