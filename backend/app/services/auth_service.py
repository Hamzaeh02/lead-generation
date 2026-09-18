import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.auth import AuthResponse, TokenResponse
from app.services.token_revocation import TokenRevocationStore, get_token_revocation_store
from app.utils.logging import get_logger
from app.utils.slugify import slugify

logger = get_logger(__name__)


class AuthService:
    def __init__(
        self, session: AsyncSession, revocation_store: TokenRevocationStore | None = None
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self._revocation_store = revocation_store

    async def register(
        self, *, email: str, password: str, full_name: str | None, workspace_name: str
    ) -> AuthResponse:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

        user = await self.users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )

        base_slug = slugify(workspace_name)
        slug = base_slug
        suffix = 1
        while await self.workspaces.get_by_slug(slug) is not None:
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        workspace = await self.workspaces.create(name=workspace_name, slug=slug)
        await self.workspaces.add_member(
            workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER
        )
        await self.session.commit()

        logger.info("user_registered", user_id=str(user.id), workspace_id=str(workspace.id))
        return self._build_auth_response(user)

    async def login(self, *, email: str, password: str) -> AuthResponse:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        logger.info("user_logged_in", user_id=str(user.id))
        return self._build_auth_response(user)

    async def refresh(self, *, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if self._revocation_store is not None and await self._revocation_store.is_revoked(
            payload["jti"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        user_id = uuid.UUID(payload["sub"])
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    def _build_auth_response(self, user: User) -> AuthResponse:
        return AuthResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            user=user,  # type: ignore[arg-type]
        )
