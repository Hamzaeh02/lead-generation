"""AI personalization provider interface (OpenAI-compatible).

The AI must only use facts explicitly passed in `source_fields`; it must
never be prompted in a way that invites inventing achievements, funding,
customers, etc. Grounding enforcement lives in the service that builds the
prompt (later phase) — this interface just defines the provider contract.
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import BaseProvider


@dataclass(frozen=True, slots=True)
class AIGenerationRequest:
    prompt_version: str
    instructions: str
    source_fields: dict[str, Any] = field(default_factory=dict)
    max_tokens: int = 400


@dataclass(frozen=True, slots=True)
class AIGenerationResult:
    text: str
    model: str
    prompt_version: str
    source_fields_used: list[str]


class AIProvider(BaseProvider):
    @abstractmethod
    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        raise NotImplementedError
