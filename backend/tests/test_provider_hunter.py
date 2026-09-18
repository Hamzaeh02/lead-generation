import httpx
import pytest

from app.providers.base import ProviderUnavailableError
from app.providers.email_finders.hunter_provider import HunterEmailFinderProvider
from app.providers.email_verifiers.base import VerificationStatus
from app.providers.email_verifiers.hunter_provider import HunterEmailVerifierProvider

pytestmark = pytest.mark.asyncio


def _client_with(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") == "test-key"
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(base_url="https://api.hunter.io", transport=httpx.MockTransport(handler))


async def test_find_email_maps_result():
    payload = {"data": {"email": "jordan@acmedental.example", "score": 92, "position": "Owner"}}
    provider = HunterEmailFinderProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.find_email(
        first_name="Jordan", last_name="Alvarez", full_name=None, company_domain="acmedental.example"
    )

    assert result is not None
    assert result.email == "jordan@acmedental.example"
    assert result.confidence.value == "found"
    assert result.metadata.provider == "hunter"


async def test_find_email_returns_none_when_no_match():
    provider = HunterEmailFinderProvider(api_key="test-key", client=_client_with({"data": {}}))

    result = await provider.find_email(
        first_name="Jordan", last_name="Alvarez", full_name=None, company_domain="acmedental.example"
    )

    assert result is None


async def test_find_email_splits_full_name_when_first_last_missing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["first_name"] = request.url.params.get("first_name")
        captured["last_name"] = request.url.params.get("last_name")
        return httpx.Response(200, json={"data": {"email": "sam@sunshineroofing.example"}})

    client = httpx.AsyncClient(base_url="https://api.hunter.io", transport=httpx.MockTransport(handler))
    provider = HunterEmailFinderProvider(api_key="test-key", client=client)

    await provider.find_email(
        first_name=None, last_name=None, full_name="Sam Chen", company_domain="sunshineroofing.example"
    )

    assert captured == {"first_name": "Sam", "last_name": "Chen"}


async def test_verify_maps_deliverable_to_valid():
    payload = {
        "data": {
            "result": "deliverable",
            "score": 95,
            "mx_records": True,
            "smtp_check": True,
            "accept_all": False,
            "disposable": False,
            "webmail": False,
            "role": False,
        }
    }
    provider = HunterEmailVerifierProvider(api_key="test-key", client=_client_with(payload))

    result = await provider.verify("jordan@acmedental.example")

    assert result.status == VerificationStatus.VALID
    assert result.score == 95
    assert result.mx_records is True
    assert result.disposable is False


async def test_verify_maps_undeliverable_to_invalid():
    provider = HunterEmailVerifierProvider(
        api_key="test-key", client=_client_with({"data": {"result": "undeliverable"}})
    )

    result = await provider.verify("bad@example.com")

    assert result.status == VerificationStatus.INVALID


async def test_verify_maps_unknown_result_to_unknown_status():
    provider = HunterEmailVerifierProvider(
        api_key="test-key", client=_client_with({"data": {"result": "something_new"}})
    )

    result = await provider.verify("weird@example.com")

    assert result.status == VerificationStatus.UNKNOWN


async def test_missing_api_key_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        HunterEmailFinderProvider(api_key="")
    with pytest.raises(ProviderUnavailableError):
        HunterEmailVerifierProvider(api_key="")
