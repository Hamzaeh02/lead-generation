"""Buying-intent signal provider interface.

Signals must always carry a concrete source reference (URL or provider
record) — the platform never infers or invents intent.
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.providers.base import BaseProvider, ProviderMetadata


class IntentSignalType(StrEnum):
    RECENT_POST = "recent_post"
    SERVICE_REQUEST = "service_request"
    FUNDING = "funding"
    FUNDING_ANNOUNCEMENT = "funding_announcement"
    HIRING = "hiring"
    NEW_JOB_POST = "new_job_post"
    JOB_CHANGE = "job_change"
    NEW_COMPANY = "new_company"
    NEW_LOCATION = "new_location"
    EXPANSION = "expansion"
    NEGATIVE_REVIEW = "negative_review"
    PRODUCT_LAUNCH = "product_launch"
    TECHNOLOGY_CHANGE = "technology_change"
    COMPETITOR_MENTION = "competitor_mention"
    ASKING_FOR_RECOMMENDATION = "asking_for_recommendation"
    ENGAGEMENT_WITH_RELEVANT_CONTENT = "engagement_with_relevant_content"
    EVENT_ATTENDANCE = "event_attendance"
    COMPANY_GROWTH = "company_growth"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class IntentSignalData:
    signal_type: IntentSignalType
    source: str
    detected_at: datetime
    metadata: ProviderMetadata
    signal_text: str | None = None
    confidence: float | None = None  # 0.0-1.0 as reported/derived from the source


class IntentProvider(BaseProvider):
    @abstractmethod
    async def discover_intent(
        self, *, company_domain: str | None = None, keywords: str | None = None
    ) -> list[IntentSignalData]:
        raise NotImplementedError
