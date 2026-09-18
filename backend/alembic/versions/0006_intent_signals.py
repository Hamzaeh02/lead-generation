"""intent_signals

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

intent_signal_type = postgresql.ENUM(
    "recent_post", "service_request", "funding", "funding_announcement", "hiring",
    "new_job_post", "job_change", "new_company", "new_location", "expansion",
    "negative_review", "product_launch", "technology_change", "competitor_mention",
    "asking_for_recommendation", "engagement_with_relevant_content", "event_attendance",
    "company_growth", "other",
    name="intent_signal_type",
    create_type=False,
)


def upgrade() -> None:
    intent_signal_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "intent_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_type", intent_signal_type, nullable=False),
        sa.Column("provider", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("signal_text", sa.String(2000), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_intent_signals_workspace_company", "intent_signals", ["workspace_id", "company_id"])


def downgrade() -> None:
    op.drop_table("intent_signals")
    intent_signal_type.drop(op.get_bind(), checkfirst=True)
