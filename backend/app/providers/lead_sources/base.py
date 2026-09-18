"""Company / local-business / website discovery provider interfaces.

Concrete implementations (SerpApiProvider, ApifyProvider, PeopleDataLabsProvider
company search, ApolloProvider organization search, ...) live alongside these
in later phases. Nothing here calls a real API.
"""
from __future__ import annotations

from abc import abstractmethod

from app.providers.base import BaseProvider, DiscoveryCriteria, NormalizedCompany


class CompanyDiscoveryProvider(BaseProvider):
    """Finds companies matching structured ICP criteria (e.g. Apollo/PDL org search)."""

    @abstractmethod
    async def discover_companies(
        self, criteria: DiscoveryCriteria
    ) -> list[NormalizedCompany]:
        """Return companies matching criteria. Never fabricates results —
        an empty list means the provider found nothing, not an error."""
        raise NotImplementedError


class LocalBusinessDiscoveryProvider(BaseProvider):
    """Finds local businesses via place/search APIs (e.g. SerpApi, Apify actors)."""

    @abstractmethod
    async def discover_local_businesses(
        self, criteria: DiscoveryCriteria
    ) -> list[NormalizedCompany]:
        raise NotImplementedError


class WebsiteDiscoveryProvider(BaseProvider):
    """Resolves a company's canonical website/domain from partial signals."""

    @abstractmethod
    async def discover_website(self, company_name: str, hint: str | None = None) -> str | None:
        raise NotImplementedError
