import dataclasses
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_superuser
from app.providers.base import ProviderCategory
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.repositories.provider_usage_repository import ProviderUsageRepository
from app.schemas.provider import ProviderConfigRead, ProviderConfigUpdate
from app.schemas.provider_usage import ProviderHealthRead, ProviderUsageRead

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderConfigRead])
async def list_providers(
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ProviderConfigRepository(session)
    return await repo.list_all()


@router.get("/usage", response_model=list[ProviderUsageRead])
async def list_provider_usage(
    provider: str | None = Query(default=None),
    category: ProviderCategory | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ProviderUsageRepository(session)
    return await repo.list_recent(provider=provider, category=category, limit=limit)


@router.get("/health", response_model=list[ProviderHealthRead])
async def provider_health(
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    usage_repo = ProviderUsageRepository(session)
    config_repo = ProviderConfigRepository(session)

    summaries = await usage_repo.health_summary()
    configs = {(c.provider, c.category): c for c in await config_repo.list_all()}

    results = []
    for summary in summaries:
        config = configs.get((summary.provider, summary.category))
        quota = config.monthly_free_quota if config else None
        quota_remaining = max(quota - summary.calls_this_month, 0) if quota is not None else None
        results.append(
            ProviderHealthRead(
                **dataclasses.asdict(summary),
                monthly_free_quota=quota,
                quota_remaining=quota_remaining,
            )
        )
    return results


@router.patch("/{provider_config_id}", response_model=ProviderConfigRead)
async def update_provider(
    provider_config_id: uuid.UUID,
    payload: ProviderConfigUpdate,
    _admin=Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ProviderConfigRepository(session)
    provider_config = await repo.get_by_id(provider_config_id)
    if provider_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(provider_config, field_name, value)

    await session.commit()
    await session.refresh(provider_config)
    return provider_config
