import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.workspace import WorkspacePlan, WorkspaceRole


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    plan: WorkspacePlan
    limits: dict[str, Any]


class WorkspaceCreate(BaseModel):
    """Creates an additional workspace — agency/freelance mode (section 77):
    one user can own/operate several client workspaces. The creator
    becomes its owner."""

    name: str
    plan: WorkspacePlan = WorkspacePlan.FREE


class WorkspaceMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    role: WorkspaceRole
    email: str | None = None


class WorkspaceMemberAdd(BaseModel):
    """Adds an *existing* registered user to the workspace by email. This
    is not an email-invitation flow (no invite token, no signup-via-link)
    — that's a larger feature not built yet; see README."""

    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceLimitsUpdate(BaseModel):
    plan: WorkspacePlan | None = None
    limits: dict[str, Any] | None = Field(default=None)
