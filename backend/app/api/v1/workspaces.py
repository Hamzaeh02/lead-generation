import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db_session,
    require_workspace_admin,
    require_workspace_member,
    require_workspace_owner,
)
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceLimitsUpdate,
    WorkspaceMemberAdd,
    WorkspaceMemberRead,
    WorkspaceMemberRoleUpdate,
    WorkspaceRead,
)
from app.utils.slugify import slugify

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    repo = WorkspaceRepository(session)
    return await repo.list_for_user(current_user.id)


@router.post("", response_model=WorkspaceRead, status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Agency/freelance mode (section 77): create an additional workspace
    for a new client. The creator becomes its owner — this is how one user
    ends up operating several separate, isolated client workspaces."""
    repo = WorkspaceRepository(session)

    base_slug = slugify(payload.name)
    slug = base_slug
    suffix = 1
    while await repo.get_by_slug(slug) is not None:
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    workspace = await repo.create(name=payload.name, slug=slug, plan=payload.plan)
    await repo.add_member(workspace_id=workspace.id, user_id=current_user.id, role=WorkspaceRole.OWNER)
    await session.commit()
    await session.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace_limits(
    workspace_id: uuid.UUID,
    payload: WorkspaceLimitsUpdate,
    _membership=Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_db_session),
):
    repo = WorkspaceRepository(session)
    workspace = await repo.get_by_id(workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")

    if payload.plan is not None:
        workspace.plan = payload.plan
    if payload.limits is not None:
        workspace.limits = payload.limits

    await session.commit()
    await session.refresh(workspace)
    return workspace


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def list_workspace_members(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = WorkspaceRepository(session)
    user_repo = UserRepository(session)
    members = await repo.list_members(workspace_id)

    results = []
    for member in members:
        user = await user_repo.get_by_id(member.user_id)
        results.append(
            WorkspaceMemberRead(
                id=member.id, user_id=member.user_id, workspace_id=member.workspace_id,
                role=member.role, email=user.email if user else None,
            )
        )
    return results


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberRead, status_code=201)
async def add_workspace_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberAdd,
    _membership=Depends(require_workspace_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """Adds an existing registered user by email — not an email-invite
    flow (see WorkspaceMemberAdd docstring)."""
    repo = WorkspaceRepository(session)
    workspace = await repo.get_by_id(workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")

    max_team_members = workspace.limits.get("max_team_members")
    if max_team_members is not None:
        current_count = await repo.count_members(workspace_id)
        if current_count >= max_team_members:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Workspace plan limit reached ({max_team_members} team members).",
            )

    user = await UserRepository(session).get_by_email(payload.email)
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No registered user with that email. They must register an account first.",
        )

    existing = await repo.get_membership(workspace_id=workspace_id, user_id=user.id)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member of this workspace")

    member = await repo.add_member(workspace_id=workspace_id, user_id=user.id, role=payload.role)
    await session.commit()
    return WorkspaceMemberRead(
        id=member.id, user_id=member.user_id, workspace_id=member.workspace_id,
        role=member.role, email=user.email,
    )


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberRead)
async def update_workspace_member_role(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: WorkspaceMemberRoleUpdate,
    _membership=Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_db_session),
):
    repo = WorkspaceRepository(session)
    member = await repo.get_member_by_id(workspace_id, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if member.role == WorkspaceRole.OWNER and payload.role != WorkspaceRole.OWNER:
        if await repo.count_owners(workspace_id) <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot demote the workspace's only owner"
            )

    member.role = payload.role
    await session.commit()
    await session.refresh(member)
    user = await UserRepository(session).get_by_id(member.user_id)
    return WorkspaceMemberRead(
        id=member.id, user_id=member.user_id, workspace_id=member.workspace_id,
        role=member.role, email=user.email if user else None,
    )


@router.delete("/{workspace_id}/members/{member_id}", status_code=204)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    _membership=Depends(require_workspace_admin),
    session: AsyncSession = Depends(get_db_session),
):
    repo = WorkspaceRepository(session)
    member = await repo.get_member_by_id(workspace_id, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if member.role == WorkspaceRole.OWNER and await repo.count_owners(workspace_id) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove the workspace's only owner")

    await repo.remove_member(member)
    await session.commit()
