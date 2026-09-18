from pydantic import BaseModel, EmailStr

from app.schemas.user import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    workspace_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    # Optional: if the client sends its refresh token too, it's revoked
    # alongside the access token. Without it, only the access token (read
    # from the Authorization header) is revoked.
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(TokenResponse):
    user: UserRead
