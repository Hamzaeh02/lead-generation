import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_editor, require_workspace_member
from app.repositories.suppression_repository import SuppressionRepository
from app.schemas.suppression import SuppressionCreate, SuppressionRead
from app.services.suppression_service import SuppressionService

router = APIRouter(prefix="/suppressions", tags=["suppressions"])


@router.get("", response_model=list[SuppressionRead])
async def list_suppressions(
    workspace_id: uuid.UUID,
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await SuppressionRepository(session).list_for_workspace(workspace_id)


@router.post("", response_model=SuppressionRead, status_code=201)
async def create_suppression(
    workspace_id: uuid.UUID,
    payload: SuppressionCreate,
    _membership=Depends(require_workspace_editor),
    session: AsyncSession = Depends(get_db_session),
):
    service = SuppressionService(session)
    suppression = await service.suppress(
        workspace_id=workspace_id, email=payload.email, reason=payload.reason
    )
    await session.commit()
    await session.refresh(suppression)
    return suppression
