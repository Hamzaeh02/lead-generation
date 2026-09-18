"""campaigns, campaign_steps, campaign_recipients, email_events, suppressions

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

campaign_status = postgresql.ENUM(
    "draft", "scheduled", "running", "paused", "completed", "cancelled",
    name="campaign_status", create_type=False,
)
recipient_status = postgresql.ENUM(
    "pending", "sent", "opened", "clicked", "replied", "bounced",
    "unsubscribed", "suppressed", "completed", "failed", name="recipient_status",
    create_type=False,
)
email_event_type = postgresql.ENUM(
    "sent", "delivered", "opened", "clicked", "replied", "bounced",
    "unsubscribed", "complained", "out_of_office", "failed", "unknown",
    name="email_event_type", create_type=False,
)
suppression_reason = postgresql.ENUM(
    "unsubscribe", "bounce", "manual", "complaint", "reply_opt_out",
    name="suppression_reason", create_type=False,
)

_TIMESTAMP_COLS = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)


def upgrade() -> None:
    bind = op.get_bind()
    campaign_status.create(bind, checkfirst=True)
    recipient_status.create(bind, checkfirst=True)
    email_event_type.create(bind, checkfirst=True)
    suppression_reason.create(bind, checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", campaign_status, nullable=False, server_default="draft"),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("from_email", sa.String(320), nullable=False),
        sa.Column("reply_to", sa.String(320), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_campaigns_workspace_id", "campaigns", ["workspace_id"])

    op.create_table(
        "campaign_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("campaign_id", "step_number", name="uq_campaign_step_number"),
    )

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "campaign_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("status", recipient_status, nullable=False, server_default="pending"),
        sa.Column("current_step_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_recipient_contact"),
    )
    op.create_index(
        "ix_campaign_recipients_due", "campaign_recipients", ["campaign_id", "status", "next_send_at"]
    )

    op.create_table(
        "email_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "campaign_recipient_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_recipients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("event_type", email_event_type, nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_email_events_recipient", "email_events", ["campaign_recipient_id"])

    op.create_table(
        "suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("reason", suppression_reason, nullable=False),
        sa.Column(
            "campaign_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True,
        ),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("workspace_id", "email", name="uq_suppression_workspace_email"),
    )


def downgrade() -> None:
    op.drop_table("suppressions")
    op.drop_table("email_events")
    op.drop_table("campaign_recipients")
    op.drop_table("campaign_steps")
    op.drop_table("campaigns")
    bind = op.get_bind()
    suppression_reason.drop(bind, checkfirst=True)
    email_event_type.drop(bind, checkfirst=True)
    recipient_status.drop(bind, checkfirst=True)
    campaign_status.drop(bind, checkfirst=True)
