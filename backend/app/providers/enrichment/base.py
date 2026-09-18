"""Company/person enrichment provider interface.

Enrichment takes a partially-known entity (e.g. just a domain, or just a
name+company) and asks a provider to fill in more fields. It never invents
data for fields the provider doesn't return.
"""
from __future__ import annotations

from abc import abstractmethod

from app.providers.base import BaseProvider, NormalizedCompany, NormalizedContact


class EnrichmentProvider(BaseProvider):
    @abstractmethod
    async def enrich_company(
        self, *, domain: str | None = None, name: str | None = None
    ) -> NormalizedCompany | None:
        raise NotImplementedError

    @abstractmethod
    async def enrich_person(
        self,
        *,
        email: str | None = None,
        linkedin_url: str | None = None,
        full_name: str | None = None,
        company_domain: str | None = None,
    ) -> NormalizedContact | None:
        raise NotImplementedError
