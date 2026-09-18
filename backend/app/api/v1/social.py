from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.social.phantombuster_provider import (
    PhantomBusterClient,
    PhantomBusterSocialProvider,
)
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.social import (
    DiscoverPostsRequest,
    DiscoverProfileRequest,
    SocialPostRead,
    SocialProfileRead,
)
from app.services.provider_usage_tracker import ProviderUsageRecorder

router = APIRouter(prefix="/social", tags=["social"])


async def _require_membership(session: AsyncSession, workspace_id, user_id) -> None:
    membership = await WorkspaceRepository(session).get_membership(
        workspace_id=workspace_id, user_id=user_id
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")


async def _get_enabled_phantombuster_provider(
    session: AsyncSession, settings: Settings
) -> PhantomBusterSocialProvider:
    registry_entry = await ProviderConfigRepository(session).get_by_provider_and_category(
        "phantombuster", ProviderCategory.SOCIAL_SIGNAL
    )
    if registry_entry is None or not registry_entry.enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provider 'phantombuster' is not enabled for category 'social_signal'.",
        )
    if not settings.PHANTOMBUSTER_API_KEY or not settings.PHANTOMBUSTER_AGENT_ID:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Provider 'phantombuster' credentials not configured "
            "(set PHANTOMBUSTER_API_KEY and PHANTOMBUSTER_AGENT_ID).",
        )
    client = PhantomBusterClient(
        api_key=settings.PHANTOMBUSTER_API_KEY, agent_id=settings.PHANTOMBUSTER_AGENT_ID
    )
    return PhantomBusterSocialProvider(client=client)


@router.post("/discover-profile", response_model=SocialProfileRead)
async def discover_profile(
    payload: DiscoverProfileRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    await _require_membership(session, payload.workspace_id, current_user.id)
    provider = await _get_enabled_phantombuster_provider(session, settings)

    async with ProviderUsageRecorder(
        session,
        provider="phantombuster",
        category=ProviderCategory.SOCIAL_SIGNAL,
        operation="discover_profile",
        workspace_id=payload.workspace_id,
    ) as usage:
        try:
            profile = await provider.discover_profile(
                full_name=payload.full_name, company_domain=payload.company_domain
            )
        except ProviderUnavailableError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider request failed: {exc}") from exc
        usage.records_returned = 1 if profile else 0

    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile found")
    return profile


@router.post("/discover-posts", response_model=list[SocialPostRead])
async def discover_posts(
    payload: DiscoverPostsRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    await _require_membership(session, payload.workspace_id, current_user.id)
    provider = await _get_enabled_phantombuster_provider(session, settings)

    async with ProviderUsageRecorder(
        session,
        provider="phantombuster",
        category=ProviderCategory.SOCIAL_SIGNAL,
        operation="discover_posts",
        workspace_id=payload.workspace_id,
    ) as usage:
        try:
            posts = await provider.discover_posts(payload.keywords, limit=payload.limit)
        except ProviderUnavailableError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider request failed: {exc}") from exc
        usage.records_returned = len(posts)

    return posts
