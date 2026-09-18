"""Hunter.io Domain Search (person discovery / decision-maker lookup).

Distinct from `email_finders/hunter_provider.py` (single name -> email
lookup): this hits `/v2/domain-search`, which returns every person Hunter
has scraped for a domain from public sources (LinkedIn, company sites,
press), each with a name, job position, seniority, and (often) an email
Hunter already found — no separate find/verify round-trip needed for these.

`decision_maker=true` is a filter Hunter's API applies server-side, based
on its own classification of the position (owner/founder/partner/GM/exec,
etc.) — this is used as the relevance signal instead of exact-string title
matching against `target_titles`, since real-world titles ("Managing
Partner", "Co-Founder, Chief People Officer") rarely match a fixed title
list exactly the way Apollo/PDL's search does.

Coverage is real but skewed: chains/multi-location businesses with a
public web footprint often have data; small single-location businesses
usually don't, because Hunter has nothing to scrape for them. An empty
result is a normal outcome, not an error.

Requires HUNTER_API_KEY.
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    DiscoveryCriteria,
    NormalizedContact,
    ProviderCategory,
    ProviderMetadata,
    ProviderUnavailableError,
)
from app.providers.http import request_json
from app.providers.people_sources.base import PersonDiscoveryProvider

_BASE_URL = "https://api.hunter.io"
# Hunter's Free plan 400s ("pagination_error") above 10 results per
# domain-search page — paid plans allow more, but there's no cheap way to
# detect the account's actual cap ahead of time, so this stays at the
# lowest common denominator rather than guessing higher and retrying.
_MAX_PAGE_SIZE = 10


class HunterPersonDiscoveryProvider(PersonDiscoveryProvider):
    name = "hunter"
    category = ProviderCategory.PERSON_DISCOVERY

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("hunter: HUNTER_API_KEY is not configured")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(15.0))

    async def discover_people(self, criteria: DiscoveryCriteria) -> list[NormalizedContact]:
        if not criteria.domain:
            return []
        return await self._domain_search(criteria.domain, decision_maker=False, limit=criteria.limit)

    async def discover_decision_makers(
        self, company_domain: str, target_titles: list[str]
    ) -> list[NormalizedContact]:
        contacts = await self._domain_search(company_domain, decision_maker=True, limit=_MAX_PAGE_SIZE)
        if not target_titles:
            return contacts

        wanted = [t.strip().lower() for t in target_titles if t.strip()]
        matched = [
            c for c in contacts if c.job_title and any(w in c.job_title.lower() for w in wanted)
        ]
        # Hunter's own decision_maker classification is a better relevance
        # signal than exact title text matching (see module docstring) —
        # fall back to the full decision-maker list when none of the
        # scraped position strings happen to contain one of the target
        # words verbatim, rather than reporting an empty result.
        return matched or contacts

    async def _domain_search(
        self, domain: str, *, decision_maker: bool, limit: int
    ) -> list[NormalizedContact]:
        params: dict = {"domain": domain, "api_key": self._api_key, "limit": min(limit, _MAX_PAGE_SIZE)}
        if decision_maker:
            params["decision_maker"] = "true"

        payload = await request_json(
            self._client, "GET", "/v2/domain-search", provider=self.name, params=params
        )
        rows = payload.get("data", {}).get("emails") or []
        return [self._to_contact(row, domain) for row in rows]

    def _to_contact(self, row: dict, domain: str) -> NormalizedContact:
        first = row.get("first_name")
        last = row.get("last_name")
        full_name = " ".join(p for p in (first, last) if p) or None
        return NormalizedContact(
            email=row.get("value"),
            phone=row.get("phone_number"),
            metadata=ProviderMetadata(
                provider=self.name,
                source_url=row.get("linkedin"),
                source_type="api",
                raw_reference=row,
            ),
            first_name=first,
            last_name=last,
            full_name=full_name,
            job_title=row.get("position"),
            seniority=row.get("seniority"),
            linkedin_url=row.get("linkedin"),
            company_domain=domain,
        )
