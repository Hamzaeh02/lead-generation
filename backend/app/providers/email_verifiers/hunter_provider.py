"""Hunter.io email verification.

Built against Hunter's documented v2 `/v2/email-verifier` endpoint
(`api_key` query param). Hunter's `result` field
(deliverable/undeliverable/risky/unknown) maps directly to our
VerificationStatus — this is real SMTP/MX/disposable-check evidence from
Hunter, not a regex/syntax check being relabeled as verification.

Requires HUNTER_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import ProviderCategory, ProviderMetadata, ProviderUnavailableError
from app.providers.email_verifiers.base import (
    EmailVerifierProvider,
    VerificationResult,
    VerificationStatus,
)
from app.providers.http import request_json

_BASE_URL = "https://api.hunter.io"

_STATUS_MAP = {
    "deliverable": VerificationStatus.VALID,
    "undeliverable": VerificationStatus.INVALID,
    "risky": VerificationStatus.RISKY,
    "unknown": VerificationStatus.UNKNOWN,
}


class HunterEmailVerifierProvider(EmailVerifierProvider):
    name = "hunter"
    category = ProviderCategory.EMAIL_VERIFIER

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("hunter: HUNTER_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(15.0))

    async def verify(self, email: str) -> VerificationResult:
        params = {"email": email, "api_key": self._api_key}
        payload = await request_json(
            self._client, "GET", "/v2/email-verifier", provider=self.name, params=params
        )
        data = payload.get("data") or {}
        status = _STATUS_MAP.get(data.get("result"), VerificationStatus.UNKNOWN)

        return VerificationResult(
            status=status,
            metadata=ProviderMetadata(provider=self.name, source_type="api", raw_reference=data),
            mx_records=data.get("mx_records"),
            smtp_check=data.get("smtp_check"),
            accept_all=data.get("accept_all"),
            disposable=data.get("disposable"),
            free_provider=data.get("webmail"),
            role_account=data.get("role"),
            score=data.get("score"),
        )
