"""Email discovery provider interface (e.g. Hunter, Apollo email finder)."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.providers.base import BaseProvider, ProviderMetadata


class EmailConfidence(StrEnum):
    CANDIDATE = "candidate"  # pattern-generated guess — never shown as verified
    FOUND = "found"  # provider claims to have found this specific address


@dataclass(frozen=True, slots=True)
class EmailCandidate:
    email: str
    confidence: EmailConfidence
    metadata: ProviderMetadata


class EmailFinderProvider(BaseProvider):
    @abstractmethod
    async def find_email(
        self,
        *,
        first_name: str | None,
        last_name: str | None,
        full_name: str | None,
        company_domain: str,
    ) -> EmailCandidate | None:
        """A pattern-generated guess must be returned with confidence=CANDIDATE,
        never marked as verified — verification is a separate provider step."""
        raise NotImplementedError
