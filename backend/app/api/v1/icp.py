import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_workspace_member
from app.repositories.icp_profile_repository import ICPProfileRepository
from app.schemas.icp_profile import (
    ICPProfileCreate,
    ICPProfileRead,
    ICPProfileUpdate,
    NLICPParseRequest,
    NLICPParseResponse,
)
from app.services.nl_icp_parser import parse_nl_icp

router = APIRouter(prefix="/icp-profiles", tags=["icp"])


@router.post("/parse", response_model=NLICPParseResponse)
async def parse_natural_language_icp(
    payload: NLICPParseRequest,
    _current_user=Depends(get_current_user),
):
    """Suggests structured ICP criteria from free text. Never persisted or
    executed automatically — the caller must review/edit and then POST to
    /icp-profiles (to save) or /search/execute (to run) explicitly."""
    return parse_nl_icp(payload.text)


@router.post("", response_model=ICPProfileRead, status_code=201)
async def create_icp_profile(
    workspace_id: uuid.UUID,
    payload: ICPProfileCreate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ICPProfileRepository(session)
    profile = repo.create(workspace_id=workspace_id, **payload.model_dump())
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("", response_model=list[ICPProfileRead])
async def list_icp_profiles(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await ICPProfileRepository(session).list_for_workspace(workspace_id)


@router.get("/{icp_profile_id}", response_model=ICPProfileRead)
async def get_icp_profile(
    icp_profile_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    profile = await ICPProfileRepository(session).get_by_id(workspace_id, icp_profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found")
    return profile


@router.patch("/{icp_profile_id}", response_model=ICPProfileRead)
async def update_icp_profile(
    icp_profile_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: ICPProfileUpdate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ICPProfileRepository(session)
    profile = await repo.get_by_id(workspace_id, icp_profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP profile not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field_name, value)

    await session.commit()
    await session.refresh(profile)
    return profile
