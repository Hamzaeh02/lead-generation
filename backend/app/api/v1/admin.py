import dataclasses
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_superuser
from app.models.user import User
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.repositories.provider_usage_repository import ProviderUsageRepository
from app.repositories.user_repository import UserRepository
from app.schemas.provider_usage import ProviderHealthRead
from app.schemas.user import SuperuserUpdate, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
async def list_users(
    _admin: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    return await UserRepository(session).list_all()


@router.patch("/users/{user_id}/superuser", response_model=UserRead)
async def update_user_superuser(
    user_id: uuid.UUID,
    payload: SuperuserUpdate,
    admin: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    """Promote/demote platform-admin access. Deliberately separate from the
    workspace-scoped RBAC roles (see require_workspace_role) — this governs
    the platform-wide /admin/* surface, not any single workspace."""
    if user_id == admin.id and not payload.is_superuser:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot remove your own superuser access"
        )

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.is_superuser = payload.is_superuser
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/providers", response_model=list[ProviderHealthRead])
async def admin_provider_panel(
    _admin: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    """Consolidated admin view of every registered (provider, category)
    pair, merging its enable/priority/quota config with its live health
    summary in one call — everything /providers, /providers/health, and
    /providers/usage expose separately, in one admin-facing response."""
    usage_repo = ProviderUsageRepository(session)
    config_repo = ProviderConfigRepository(session)

    summaries = {(s.provider, s.category): s for s in await usage_repo.health_summary()}
    configs = await config_repo.list_all()

    results = []
    for config in configs:
        summary = summaries.get((config.provider, config.category))
        if summary is not None:
            results.append(
                ProviderHealthRead(
                    **dataclasses.asdict(summary),
                    monthly_free_quota=config.monthly_free_quota,
                    quota_remaining=(
                        max(config.monthly_free_quota - summary.calls_this_month, 0)
                        if config.monthly_free_quota is not None
                        else None
                    ),
                )
            )
        else:
            results.append(
                ProviderHealthRead(
                    provider=config.provider,
                    category=config.category,
                    total_calls=0,
                    success_count=0,
                    failure_count=0,
                    success_rate=0.0,
                    avg_duration_ms=0.0,
                    last_success_at=None,
                    last_failure_at=None,
                    last_error=None,
                    calls_this_month=0,
                    monthly_free_quota=config.monthly_free_quota,
                    quota_remaining=config.monthly_free_quota,
                )
            )
    return results
