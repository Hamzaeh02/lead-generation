from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_bearer_payload,
    get_current_user,
    get_db_session,
    login_rate_limit,
    refresh_rate_limit,
    register_rate_limit,
)
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import AuthService
from app.services.token_revocation import TokenRevocationStore, get_token_revocation_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=AuthResponse, status_code=201, dependencies=[Depends(register_rate_limit)]
)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db_session)):
    service = AuthService(session)
    return await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        workspace_name=payload.workspace_name,
    )


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(login_rate_limit)])
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    service = AuthService(session)
    return await service.login(email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(refresh_rate_limit)])
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    revocation_store: TokenRevocationStore = Depends(get_token_revocation_store),
):
    service = AuthService(session, revocation_store)
    return await service.refresh(refresh_token=payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    access_payload: dict[str, Any] = Depends(get_bearer_payload),
    _current_user: User = Depends(get_current_user),
    revocation_store: TokenRevocationStore = Depends(get_token_revocation_store),
):
    """Revokes the current access token immediately, plus the refresh
    token if the caller sends it — server-side revocation via a Redis
    denylist keyed by each token's `jti`, not just a client-side discard
    (see README §16)."""
    access_ttl = int(access_payload["exp"] - access_payload["iat"])
    await revocation_store.revoke(access_payload["jti"], ttl_seconds=access_ttl)

    if payload.refresh_token:
        refresh_payload = decode_token(payload.refresh_token)
        if refresh_payload is not None and refresh_payload.get("type") == "refresh":
            refresh_ttl = int(refresh_payload["exp"] - refresh_payload["iat"])
            await revocation_store.revoke(refresh_payload["jti"], ttl_seconds=refresh_ttl)

    return None


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
