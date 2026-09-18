"""Groq AI provider (chat completions, JSON output) — free-tier alternative to OpenAI.

Groq's API is OpenAI-compatible (`Authorization: Bearer`,
`/openai/v1/chat/completions`, same `response_format: {"type": "json_object"}`
JSON mode), so this mirrors `openai_provider.py` almost exactly and differs
only in base URL and default model. Groq's free tier (as of 2026: no
credit card, ~30 requests/minute) runs open-weight models it hosts itself
(its catalog has shifted over time — verify current model IDs via
GET /openai/v1/models before assuming any name below still exists) — this
is the zero-cost default for AI personalization until/unless a paid
provider is configured.

Default model is `qwen/qwen3.8-27b`, chosen over Groq's reasoning models
(e.g. `openai/gpt-oss-120b`) specifically because it returns plain content
directly — reasoning models spend part of `max_tokens` on a hidden
`reasoning` field first, which can leave nothing for the actual JSON
output and makes response length unpredictable for this structured-output
use case.

Same grounding caveat as openai_provider.py: this provider just calls the
model with whatever instructions/facts it's given. The no-fabrication
guarantee lives in the caller (PersonalizationService).

Requires GROQ_API_KEY.
"""
from __future__ import annotations

import json

import httpx

from app.providers.ai.base import AIGenerationRequest, AIGenerationResult, AIProvider
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.http import request_json

_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(AIProvider):
    name = "groq"
    category = ProviderCategory.AI

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen/qwen3.8-27b",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("groq: GROQ_API_KEY is not configured")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(30.0))

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        facts = json.dumps(request.source_fields, indent=2)
        payload = await request_json(
            self._client,
            "POST",
            "/chat/completions",
            provider=self.name,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": request.instructions},
                    {"role": "user", "content": f"Known facts (JSON):\n{facts}"},
                ],
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderUnavailableError("groq: response contained no choices")
        content = choices[0].get("message", {}).get("content")
        if not content:
            raise ProviderUnavailableError("groq: response message had no content")

        return AIGenerationResult(
            text=content,
            model=payload.get("model", self._model),
            prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )
