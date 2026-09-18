from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.core.config import Settings, get_settings
from app.models.user import User
from app.providers.base import DiscoveryCriteria
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.search import SearchExecuteRequest, SearchExecuteResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/execute", response_model=SearchExecuteResponse)
async def execute_search(
    payload: SearchExecuteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    membership = await WorkspaceRepository(session).get_membership(
        workspace_id=payload.workspace_id, user_id=current_user.id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace"
        )

    criteria = DiscoveryCriteria(**payload.criteria.model_dump())
    service = SearchService(session, settings)
    result = await service.execute(
        workspace_id=payload.workspace_id,
        provider_name=payload.provider,
        category=payload.category,
        criteria=criteria,
    )

    return SearchExecuteResponse(
        provider=payload.provider,
        category=payload.category,
        **result,
    )
