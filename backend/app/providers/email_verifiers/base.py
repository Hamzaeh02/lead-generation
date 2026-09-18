"""Email verification provider interface (e.g. Hunter verify, future providers)."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.providers.base import BaseProvider, ProviderMetadata


class VerificationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    RISKY = "risky"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: VerificationStatus
    metadata: ProviderMetadata
    mx_records: bool | None = None
    smtp_check: bool | None = None
    accept_all: bool | None = None
    disposable: bool | None = None
    free_provider: bool | None = None
    role_account: bool | None = None
    score: int | None = None  # 0-100, provider-reported confidence if available


class EmailVerifierProvider(BaseProvider):
    @abstractmethod
    async def verify(self, email: str) -> VerificationResult:
        """Never treat regex/syntax validation alone as verification — this
        must reflect actual provider evidence (MX/SMTP/disposable checks)."""
        raise NotImplementedError
