import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_superuser
from app.repositories.actor_config_repository import ActorConfigRepository
from app.schemas.actor_config import ActorConfigCreate, ActorConfigRead, ActorConfigUpdate

router = APIRouter(prefix="/apify/actors", tags=["apify"])


@router.get("", response_model=list[ActorConfigRead])
async def list_actor_configs(
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await ActorConfigRepository(session).list_all()


@router.post("", response_model=ActorConfigRead, status_code=201)
async def create_actor_config(
    payload: ActorConfigCreate,
    _admin=Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    actor_config = ActorConfigRepository(session).create(**payload.model_dump())
    await session.commit()
    await session.refresh(actor_config)
    return actor_config


@router.patch("/{actor_config_id}", response_model=ActorConfigRead)
async def update_actor_config(
    actor_config_id: uuid.UUID,
    payload: ActorConfigUpdate,
    _admin=Depends(require_superuser),
    session: AsyncSession = Depends(get_db_session),
):
    repo = ActorConfigRepository(session)
    actor_config = await repo.get_by_id(actor_config_id)
    if actor_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor config not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(actor_config, field_name, value)

    await session.commit()
    await session.refresh(actor_config)
    return actor_config
