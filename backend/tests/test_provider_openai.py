import json

import httpx
import pytest

from app.providers.ai.base import AIGenerationRequest
from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.base import ProviderUnavailableError

pytestmark = pytest.mark.asyncio


def _client_with(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer test-key"
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(base_url="https://api.openai.com", transport=httpx.MockTransport(handler))


async def test_generate_returns_content_and_metadata():
    content = json.dumps({"subject": "Quick question", "body": "Hi Jordan, ..."})
    payload = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": content}}],
    }
    provider = OpenAIProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.generate(
        AIGenerationRequest(
            prompt_version="v1",
            instructions="Write a truthful email.",
            source_fields={"company_name": "Acme Dental Group"},
        )
    )

    assert result.text == content
    assert result.model == "gpt-4o-mini"
    assert result.prompt_version == "v1"
    assert result.source_fields_used == ["company_name"]


async def test_generate_sends_facts_and_json_response_format():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"model": "gpt-4o-mini", "choices": [{"message": {"content": "{}"}}]},
        )

    provider = OpenAIProvider(
        api_key="test-key",
        client=httpx.AsyncClient(base_url="https://api.openai.com", transport=httpx.MockTransport(handler)),
    )

    await provider.generate(
        AIGenerationRequest(
            prompt_version="v1",
            instructions="SYSTEM RULES",
            source_fields={"company_name": "Acme"},
        )
    )

    body = captured["body"]
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["content"] == "SYSTEM RULES"
    assert "Acme" in body["messages"][1]["content"]


async def test_generate_raises_on_empty_choices():
    provider = OpenAIProvider(api_key="test-key", client=_client_with({"model": "gpt-4o-mini", "choices": []}))

    with pytest.raises(ProviderUnavailableError):
        await provider.generate(
            AIGenerationRequest(prompt_version="v1", instructions="x", source_fields={})
        )


async def test_missing_api_key_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        OpenAIProvider(api_key="")
