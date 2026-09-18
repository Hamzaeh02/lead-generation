"""Builds a concrete provider instance for a (provider name, category) pair.

Returns None when the required API key isn't configured — callers turn
that into a clear "provider not configured" response rather than a crash.
This is the one place in the codebase that knows about concrete provider
classes; everything else depends only on the ABCs in app/providers/base.py.
"""
from __future__ import annotations

from app.core.config import Settings
# from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.ai.groq_provider import GroqProvider
from app.providers.base import BaseProvider, ProviderCategory, ProviderUnavailableError
from app.providers.email_finders.hunter_provider import HunterEmailFinderProvider
# from app.providers.email_senders.smtp_provider import SMTPEmailSenderProvider
from app.providers.email_verifiers.hunter_provider import HunterEmailVerifierProvider
# from app.providers.enrichment.pdl_provider import PeopleDataLabsEnrichmentProvider
# from app.providers.lead_sources.apollo_provider import ApolloCompanyDiscoveryProvider
from app.providers.lead_sources.osm_provider import OSMLocalBusinessProvider
# from app.providers.lead_sources.pdl_provider import PeopleDataLabsCompanyDiscoveryProvider
from app.providers.lead_sources.serpapi_provider import SerpApiLocalBusinessProvider
# from app.providers.people_sources.apollo_provider import ApolloPersonDiscoveryProvider
from app.providers.people_sources.hunter_provider import HunterPersonDiscoveryProvider
from app.providers.people_sources.pdl_provider import PeopleDataLabsPersonDiscoveryProvider

# Pipeline trimmed down for now to: serpapi/openstreetmap (local business
# discovery) -> hunter (email finder + verifier) only. Apollo, PDL, OpenAI,
# and SMTP builders are commented out (not deleted) so they're inert but
# easy to bring back — the matching registry rows are disabled to match.
# env_var is None for providers that need no credentials at all (e.g. OSM) —
# those are always buildable, never gated by a missing-API-key check.
_BUILDERS: dict[tuple[str, ProviderCategory], tuple[str | None, type]] = {
    # ("apollo", ProviderCategory.COMPANY_DISCOVERY): ("APOLLO_API_KEY", ApolloCompanyDiscoveryProvider),
    # ("apollo", ProviderCategory.PERSON_DISCOVERY): ("APOLLO_API_KEY", ApolloPersonDiscoveryProvider),
    # ("people_data_labs", ProviderCategory.COMPANY_DISCOVERY): (
    #     "PDL_API_KEY", PeopleDataLabsCompanyDiscoveryProvider,
    # ),
    ("people_data_labs", ProviderCategory.PERSON_DISCOVERY): (
        "PDL_API_KEY", PeopleDataLabsPersonDiscoveryProvider,
    ),
    ("hunter", ProviderCategory.PERSON_DISCOVERY): ("HUNTER_API_KEY", HunterPersonDiscoveryProvider),
    # ("people_data_labs", ProviderCategory.ENRICHMENT): (
    #     "PDL_API_KEY", PeopleDataLabsEnrichmentProvider,
    # ),
    ("serpapi", ProviderCategory.LOCAL_BUSINESS_DISCOVERY): (
        "SERPAPI_API_KEY", SerpApiLocalBusinessProvider,
    ),
    ("hunter", ProviderCategory.EMAIL_FINDER): ("HUNTER_API_KEY", HunterEmailFinderProvider),
    ("hunter", ProviderCategory.EMAIL_VERIFIER): ("HUNTER_API_KEY", HunterEmailVerifierProvider),
    ("openstreetmap", ProviderCategory.LOCAL_BUSINESS_DISCOVERY): (None, OSMLocalBusinessProvider),
    # ("openai", ProviderCategory.AI): ("OPENAI_API_KEY", OpenAIProvider),
    ("groq", ProviderCategory.AI): ("GROQ_API_KEY", GroqProvider),
    # ("smtp", ProviderCategory.EMAIL_SENDER): ("SMTP_HOST", SMTPEmailSenderProvider),
}


def required_env_var(provider_name: str, category: ProviderCategory) -> str | None:
    entry = _BUILDERS.get((provider_name, category))
    return entry[0] if entry else None


def build_provider(
    provider_name: str, category: ProviderCategory, settings: Settings
) -> BaseProvider | None:
    entry = _BUILDERS.get((provider_name, category))
    if entry is None:
        return None
    env_var, provider_cls = entry
    if env_var is None:
        return provider_cls()

    # SMTP and OpenAI builders were here (needed non-standard construction:
    # SMTP takes host/port/username/password, OpenAI takes a model) — both
    # commented out above along with their _BUILDERS entries, so the
    # branches that referenced them are removed too. Restore alongside the
    # imports/_BUILDERS entries if re-enabling either provider.

    api_key = getattr(settings, env_var, None)
    if not api_key:
        return None
    if provider_cls is GroqProvider:
        return GroqProvider(api_key=api_key, model=settings.GROQ_MODEL)
    return provider_cls(api_key=api_key)
