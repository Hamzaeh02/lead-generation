"""Public unsubscribe endpoint (section 45) — mounted at the root, not
under /api/v1, matching the spec's literal `/unsubscribe/{token}` path.
No authentication: the signed token itself is the credential."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.suppression import SuppressionReason
from app.repositories.contact_repository import ContactRepository
from app.services.suppression_service import SuppressionService
from app.services.unsubscribe_token_service import decode_unsubscribe_token

router = APIRouter(tags=["unsubscribe"])


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str, session: AsyncSession = Depends(get_db_session)):
    decoded = decode_unsubscribe_token(token)
    if decoded is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired unsubscribe link")
    workspace_id, contact_id = decoded

    contact = await ContactRepository(session).get_by_id(workspace_id, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

    if contact.email:
        await SuppressionService(session).suppress(
            workspace_id=workspace_id, email=contact.email, reason=SuppressionReason.UNSUBSCRIBE
        )
    await session.commit()

    return HTMLResponse("<html><body><p>You have been unsubscribed.</p></body></html>")
