import httpx
import pytest

from app.providers.base import ProviderUnavailableError
from app.providers.social.phantombuster_provider import (
    PhantomBusterClient,
    PhantomBusterSocialProvider,
)

pytestmark = pytest.mark.asyncio


def _sequenced_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        return response

    return httpx.MockTransport(handler)


async def test_run_and_collect_full_cycle():
    launch_response = httpx.Response(200, json={"containerId": "c-1"})
    poll_response = httpx.Response(
        200, json={"status": "finished", "resultObject": '[{"fullName": "Jordan Alvarez"}]'}
    )
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([launch_response, poll_response]),
        ),
        poll_interval_seconds=0,
    )

    rows = await client.run_and_collect({"search": "Jordan"})

    assert rows == [{"fullName": "Jordan Alvarez"}]


async def test_poll_raises_on_error_status():
    launch_response = httpx.Response(200, json={"containerId": "c-1"})
    error_response = httpx.Response(200, json={"status": "error"})
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([launch_response, error_response]),
        ),
        poll_interval_seconds=0,
    )

    with pytest.raises(ProviderUnavailableError):
        await client.run_and_collect({})


async def test_poll_gives_up_after_max_attempts():
    running_response = httpx.Response(200, json={"status": "running"})
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([running_response]),
        ),
        poll_interval_seconds=0,
        max_poll_attempts=2,
    )

    with pytest.raises(ProviderUnavailableError):
        await client.poll("c-1")


async def test_missing_credentials_raises_immediately():
    with pytest.raises(ProviderUnavailableError):
        PhantomBusterClient(api_key="", agent_id="agent-1")
    with pytest.raises(ProviderUnavailableError):
        PhantomBusterClient(api_key="key", agent_id="")


async def test_discover_profile_maps_fields():
    launch_response = httpx.Response(200, json={"containerId": "c-1"})
    poll_response = httpx.Response(
        200,
        json={
            "status": "finished",
            "resultObject": '[{"fullName": "Jordan Alvarez", "profileUrl": "https://linkedin.com/in/jordan", "headline": "Owner at Acme Dental"}]',
        },
    )
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([launch_response, poll_response]),
        ),
        poll_interval_seconds=0,
    )
    provider = PhantomBusterSocialProvider(client=client)

    profile = await provider.discover_profile(full_name="Jordan Alvarez")

    assert profile is not None
    assert profile.profile_url == "https://linkedin.com/in/jordan"
    assert profile.display_name == "Jordan Alvarez"
    assert profile.headline == "Owner at Acme Dental"
    assert profile.metadata.provider == "phantombuster"


async def test_discover_profile_returns_none_without_profile_url():
    launch_response = httpx.Response(200, json={"containerId": "c-1"})
    poll_response = httpx.Response(
        200, json={"status": "finished", "resultObject": '[{"fullName": "No URL"}]'}
    )
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([launch_response, poll_response]),
        ),
        poll_interval_seconds=0,
    )
    provider = PhantomBusterSocialProvider(client=client)

    profile = await provider.discover_profile(full_name="No URL")

    assert profile is None


async def test_discover_posts_maps_fields_and_skips_rows_without_url():
    launch_response = httpx.Response(200, json={"containerId": "c-1"})
    poll_response = httpx.Response(
        200,
        json={
            "status": "finished",
            "resultObject": (
                '[{"postUrl": "https://linkedin.com/post/1", "text": "We are hiring!", '
                '"authorProfileUrl": "https://linkedin.com/in/jordan", "timestamp": "2026-08-01"},'
                '{"text": "no url here"}]'
            ),
        },
    )
    client = PhantomBusterClient(
        api_key="key",
        agent_id="agent-1",
        client=httpx.AsyncClient(
            base_url="https://api.phantombuster.com",
            transport=_sequenced_transport([launch_response, poll_response]),
        ),
        poll_interval_seconds=0,
    )
    provider = PhantomBusterSocialProvider(client=client)

    posts = await provider.discover_posts("hiring", limit=10)

    assert len(posts) == 1
    assert posts[0].post_url == "https://linkedin.com/post/1"
    assert posts[0].text == "We are hiring!"
