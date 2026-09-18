"""provider_usage (cost tracking + provider health basis)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(name="provider_category", create_type=False)


def upgrade() -> None:
    op.create_table(
        "provider_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("category", provider_category, nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("records_returned", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_provider_usage_provider_category", "provider_usage", ["provider", "category"])
    op.create_index("ix_provider_usage_occurred_at", "provider_usage", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("provider_usage")
