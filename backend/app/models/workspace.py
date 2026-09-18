from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, str_enum_values

if TYPE_CHECKING:
    from app.models.user import User


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkspacePlan(StrEnum):
    """Section 78 (SaaS billing prep) — no pricing is hard-coded anywhere;
    this is purely a label plus a configurable `limits` blob an operator
    sets. There is no billing/payment integration behind this."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"
    ENTERPRISE = "enterprise"


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tenant boundary. Every customer-owned record hangs off a workspace_id."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plan: Mapped[WorkspacePlan] = mapped_column(
        Enum(WorkspacePlan, name="workspace_plan", values_callable=str_enum_values), default=WorkspacePlan.FREE, nullable=False
    )
    # e.g. {"max_team_members": 5, "max_campaigns": 10}. Null/missing key
    # means "no limit enforced" — nothing here is enforced unless set.
    limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    members: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, name="workspace_role", values_callable=str_enum_values), default=WorkspaceRole.MEMBER, nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")
