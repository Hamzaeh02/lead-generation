"""actor_configs (Apify actor registry)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(name="provider_category", create_type=False)


def upgrade() -> None:
    op.create_table(
        "actor_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("category", provider_category, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_actor_configs_category", "actor_configs", ["category"])

    # 0002 only seeded (apify, local_business_discovery); apify also supports
    # company_discovery via a registered actor, so add that registry row too.
    provider_configs = sa.table(
        "provider_configs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("provider", sa.String),
        sa.column("category", provider_category),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
    )
    import uuid as _uuid

    op.bulk_insert(
        provider_configs,
        [
            {
                "id": _uuid.uuid4(),
                "provider": "apify",
                "category": "company_discovery",
                "enabled": False,
                "priority": 2,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("actor_configs")
