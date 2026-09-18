"""Person / decision-maker discovery provider interfaces."""
from __future__ import annotations

from abc import abstractmethod

from app.providers.base import BaseProvider, DiscoveryCriteria, NormalizedContact


class PersonDiscoveryProvider(BaseProvider):
    """Finds people matching structured criteria (title, seniority, company, ...)."""

    @abstractmethod
    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        raise NotImplementedError

    @abstractmethod
    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        """Company -> decision-makers lookup (e.g. Apollo org employees filtered by title)."""
        raise NotImplementedError
