from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_usage import ProviderUsage
from app.providers.base import ProviderCategory


@dataclass(frozen=True, slots=True)
class ProviderHealthSummary:
    provider: str
    category: ProviderCategory
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration_ms: float
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error: str | None
    calls_this_month: int


class ProviderUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create(self, **fields: Any) -> ProviderUsage:
        usage = ProviderUsage(**fields)
        self.session.add(usage)
        return usage

    async def list_recent(
        self,
        *,
        provider: str | None = None,
        category: ProviderCategory | None = None,
        limit: int = 100,
    ) -> list[ProviderUsage]:
        stmt = select(ProviderUsage).order_by(ProviderUsage.occurred_at.desc()).limit(limit)
        if provider:
            stmt = stmt.where(ProviderUsage.provider == provider)
        if category:
            stmt = stmt.where(ProviderUsage.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def calls_this_month(self, provider: str, category: ProviderCategory) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count()).where(
                ProviderUsage.provider == provider,
                ProviderUsage.category == category,
                ProviderUsage.occurred_at >= month_start,
            )
        )
        return result.scalar_one()

    async def health_summary(self) -> list[ProviderHealthSummary]:
        rows = await self.session.execute(
            select(
                ProviderUsage.provider,
                ProviderUsage.category,
                func.count().label("total_calls"),
                func.sum(case((ProviderUsage.success.is_(True), 1), else_=0)).label("success_count"),
                func.avg(ProviderUsage.duration_ms).label("avg_duration_ms"),
                func.max(
                    case((ProviderUsage.success.is_(True), ProviderUsage.occurred_at))
                ).label("last_success_at"),
                func.max(
                    case((ProviderUsage.success.is_(False), ProviderUsage.occurred_at))
                ).label("last_failure_at"),
            ).group_by(ProviderUsage.provider, ProviderUsage.category)
        )

        summaries: list[ProviderHealthSummary] = []
        for provider, category, total_calls, success_count, avg_duration_ms, last_success_at, last_failure_at in rows:
            success_count = success_count or 0
            last_error = None
            if last_failure_at is not None:
                last_error = await self._last_error(provider, category)
            summaries.append(
                ProviderHealthSummary(
                    provider=provider,
                    category=category,
                    total_calls=total_calls,
                    success_count=success_count,
                    failure_count=total_calls - success_count,
                    success_rate=round(success_count / total_calls, 4) if total_calls else 0.0,
                    avg_duration_ms=round(avg_duration_ms, 2) if avg_duration_ms is not None else 0.0,
                    last_success_at=last_success_at,
                    last_failure_at=last_failure_at,
                    last_error=last_error,
                    calls_this_month=await self.calls_this_month(provider, category),
                )
            )
        return summaries

    async def _last_error(self, provider: str, category: ProviderCategory) -> str | None:
        result = await self.session.execute(
            select(ProviderUsage.error)
            .where(
                ProviderUsage.provider == provider,
                ProviderUsage.category == category,
                ProviderUsage.success.is_(False),
            )
            .order_by(ProviderUsage.occurred_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
