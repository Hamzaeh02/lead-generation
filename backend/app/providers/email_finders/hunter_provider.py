"""Hunter.io email finding.

Built against Hunter's documented, stable v2 REST API (`api_key` query
param, `/v2/email-finder`). Hunter's finder combines pattern-matching with
its own confidence scoring — it is treated as EmailConfidence.FOUND (a
specific claimed address), never CANDIDATE (a raw unverified guess) and
never "verified" — actual verification is a separate step
(HunterEmailVerifierProvider / EmailVerificationOrchestrator).

Requires HUNTER_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import ProviderCategory, ProviderMetadata, ProviderUnavailableError
from app.providers.email_finders.base import EmailCandidate, EmailConfidence, EmailFinderProvider
from app.providers.http import request_json

_BASE_URL = "https://api.hunter.io"


class HunterEmailFinderProvider(EmailFinderProvider):
    name = "hunter"
    category = ProviderCategory.EMAIL_FINDER

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("hunter: HUNTER_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(15.0))

    async def find_email(
        self,
        *,
        first_name: str | None,
        last_name: str | None,
        full_name: str | None,
        company_domain: str,
    ) -> EmailCandidate | None:
        params = {"domain": company_domain, "api_key": self._api_key}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if not first_name and not last_name and full_name:
            parts = full_name.split(maxsplit=1)
            params["first_name"] = parts[0]
            if len(parts) > 1:
                params["last_name"] = parts[1]

        payload = await request_json(
            self._client, "GET", "/v2/email-finder", provider=self.name, params=params
        )
        data = payload.get("data") or {}
        email = data.get("email")
        if not email:
            return None

        return EmailCandidate(
            email=email,
            confidence=EmailConfidence.FOUND,
            metadata=ProviderMetadata(
                provider=self.name,
                source_type="api",
                raw_reference=data,
            ),
        )
