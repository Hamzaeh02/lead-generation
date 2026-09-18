import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_workspace_member
from app.schemas.analytics import AnalyticsOverview
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    workspace_id: uuid.UUID,
    icp_profile_id: uuid.UUID | None = Query(default=None),
    _membership=Depends(require_workspace_member),
    session: AsyncSession = Depends(get_db_session),
):
    return await AnalyticsService(session).overview(workspace_id, icp_profile_id=icp_profile_id)
