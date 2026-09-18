"""PhantomBuster social signal provider.

Built against PhantomBuster's documented REST API (`X-Phantombuster-Key`
header, `/api/v2/agents/launch`, `/api/v2/containers/fetch`) — launch/poll/
fetch, the same pattern as ApifyClient. Not verified against a live account
(no network access here); check `raw_reference` on real results before
trusting the field mapping.

Only launches a Phantom the user has already configured in their own
PhantomBuster account (`PHANTOMBUSTER_AGENT_ID`) — this never attempts to
build automation that bypasses LinkedIn/platform auth, rate limits, or
anti-automation controls. The Phantom's own configuration is the user's
responsibility to keep within the target platform's terms.

Requires PHANTOMBUSTER_API_KEY and PHANTOMBUSTER_AGENT_ID.
"""
from __future__ import annotations

import asyncio
import json

import httpx

from app.providers.base import ProviderCategory, ProviderMetadata, ProviderUnavailableError
from app.providers.http import request_json
from app.providers.social.base import SocialPost, SocialProfile, SocialSignalProvider

_BASE_URL = "https://api.phantombuster.com"
_TERMINAL_STATUSES = {"finished", "error"}


class PhantomBusterClient:
    def __init__(
        self,
        *,
        api_key: str,
        agent_id: str,
        client: httpx.AsyncClient | None = None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 30,
    ) -> None:
        if not api_key or not agent_id:
            raise ProviderUnavailableError(
                "phantombuster: PHANTOMBUSTER_API_KEY / PHANTOMBUSTER_AGENT_ID not configured"
            )
        self._api_key = api_key
        self._agent_id = agent_id
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(15.0))
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts

    def _headers(self) -> dict:
        return {"X-Phantombuster-Key": self._api_key}

    async def launch(self, argument: dict) -> str:
        payload = await request_json(
            self._client,
            "POST",
            "/api/v2/agents/launch",
            provider="phantombuster",
            headers=self._headers(),
            json={"id": self._agent_id, "argument": argument},
        )
        container_id = payload.get("containerId")
        if not container_id:
            raise ProviderUnavailableError("phantombuster: launch response missing containerId")
        return container_id

    async def poll(self, container_id: str) -> dict:
        for attempt in range(self._max_poll_attempts):
            payload = await request_json(
                self._client,
                "GET",
                "/api/v2/containers/fetch",
                provider="phantombuster",
                headers=self._headers(),
                params={"id": container_id},
            )
            status = payload.get("status")
            if status in _TERMINAL_STATUSES:
                if status != "finished":
                    raise ProviderUnavailableError(
                        f"phantombuster: container {container_id} ended with status {status}"
                    )
                return payload
            if attempt < self._max_poll_attempts - 1:
                await asyncio.sleep(self._poll_interval_seconds)
        raise ProviderUnavailableError(f"phantombuster: container {container_id} did not finish in time")

    async def run_and_collect(self, argument: dict) -> list[dict]:
        container_id = await self.launch(argument)
        payload = await self.poll(container_id)
        result_object = payload.get("resultObject")
        if not result_object:
            return []
        try:
            parsed = json.loads(result_object) if isinstance(result_object, str) else result_object
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else [parsed]


def _first(row: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


_PROFILE_URL_KEYS = ("profileUrl", "linkedinUrl", "url", "profile_url")
_NAME_KEYS = ("fullName", "name", "title")
_HEADLINE_KEYS = ("headline", "title", "description")
_POST_URL_KEYS = ("postUrl", "url", "link")
_TEXT_KEYS = ("text", "postContent", "description")
_AUTHOR_URL_KEYS = ("profileUrl", "authorProfileUrl", "authorUrl")
_POSTED_AT_KEYS = ("timestamp", "postedAt", "date")


class PhantomBusterSocialProvider(SocialSignalProvider):
    name = "phantombuster"
    category = ProviderCategory.SOCIAL_SIGNAL

    def __init__(self, *, client: PhantomBusterClient) -> None:
        super().__init__()
        self._client = client

    async def discover_profile(
        self, *, full_name: str | None = None, company_domain: str | None = None
    ) -> SocialProfile | None:
        rows = await self._client.run_and_collect(
            {"search": full_name, "companyDomain": company_domain}
        )
        if not rows:
            return None
        row = rows[0]
        profile_url = _first(row, _PROFILE_URL_KEYS)
        if not profile_url:
            return None
        return SocialProfile(
            platform="linkedin",
            profile_url=profile_url,
            display_name=_first(row, _NAME_KEYS),
            headline=_first(row, _HEADLINE_KEYS),
            metadata=ProviderMetadata(
                provider=self.name, source_type="phantombuster_agent", raw_reference=row
            ),
        )

    async def discover_posts(self, keywords: str, limit: int = 25) -> list[SocialPost]:
        rows = await self._client.run_and_collect({"search": keywords, "numberOfResults": limit})
        posts: list[SocialPost] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            post_url = _first(row, _POST_URL_KEYS)
            if not post_url:
                continue
            posts.append(
                SocialPost(
                    platform="linkedin",
                    post_url=post_url,
                    author_profile_url=_first(row, _AUTHOR_URL_KEYS),
                    text=_first(row, _TEXT_KEYS),
                    posted_at=_first(row, _POSTED_AT_KEYS),
                    metadata=ProviderMetadata(
                        provider=self.name, source_type="phantombuster_agent", raw_reference=row
                    ),
                )
            )
        return posts
