import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_member
from app.repositories.tag_repository import TagRepository
from app.schemas.tag import TagCreate, TagRead

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
async def list_tags(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await TagRepository(session).list_for_workspace(workspace_id)


@router.post("", response_model=TagRead, status_code=201)
async def create_tag(
    workspace_id: uuid.UUID,
    payload: TagCreate,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    repo = TagRepository(session)
    existing = await repo.get_by_name(workspace_id, payload.name)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tag already exists")

    tag = repo.create(workspace_id=workspace_id, name=payload.name)
    await session.commit()
    await session.refresh(tag)
    return tag
