"""workspaces.plan + workspaces.limits (section 78 SaaS plan/limits prep)

No pricing or billing integration is added here — plan is a label and
limits is an operator-set JSON blob, both purely informational unless a
specific limit key is read and enforced in application code (see
POST /workspaces/{id}/members, which enforces limits.max_team_members).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

workspace_plan = postgresql.ENUM(
    "free", "starter", "professional", "agency", "enterprise",
    name="workspace_plan", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    workspace_plan.create(bind, checkfirst=True)

    op.add_column(
        "workspaces",
        sa.Column("plan", workspace_plan, nullable=False, server_default="free"),
    )
    op.add_column(
        "workspaces",
        sa.Column("limits", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "limits")
    op.drop_column("workspaces", "plan")
    workspace_plan.drop(op.get_bind(), checkfirst=True)
