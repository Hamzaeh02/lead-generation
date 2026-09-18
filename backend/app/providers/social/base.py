"""Social signal provider interface (LinkedIn, X, Facebook, Instagram, Reddit, YouTube, ...).

Every concrete implementation must use an official API, licensed data, or an
authorized provider workflow — never a mechanism designed to bypass a
platform's auth/rate-limit/anti-automation controls.
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from app.providers.base import BaseProvider, ProviderMetadata


@dataclass(frozen=True, slots=True)
class SocialProfile:
    platform: str
    profile_url: str
    display_name: str | None
    headline: str | None
    metadata: ProviderMetadata


@dataclass(frozen=True, slots=True)
class SocialPost:
    platform: str
    post_url: str
    author_profile_url: str | None
    text: str | None
    posted_at: str | None  # ISO 8601 string as returned by the provider
    metadata: ProviderMetadata


class SocialSignalProvider(BaseProvider):
    @abstractmethod
    async def discover_profile(
        self, *, full_name: str | None = None, company_domain: str | None = None
    ) -> SocialProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def discover_posts(self, keywords: str, limit: int = 25) -> list[SocialPost]:
        raise NotImplementedError
