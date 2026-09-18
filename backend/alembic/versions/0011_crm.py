"""CRM: contacts.status, notes, tasks, tags, lead_tags

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

lead_status = postgresql.ENUM(
    "new", "verified", "ready_for_outreach", "contacted", "opened", "clicked",
    "replied", "interested", "meeting", "won", "lost", "unsubscribed", "bounced",
    name="lead_status", create_type=False,
)

_TIMESTAMP_COLS = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)


def upgrade() -> None:
    bind = op.get_bind()
    lead_status.create(bind, checkfirst=True)

    op.add_column(
        "contacts", sa.Column("status", lead_status, nullable=False, server_default="new")
    )
    op.create_index("ix_contacts_workspace_status", "contacts", ["workspace_id", "status"])

    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_notes_contact_id", "notes", ["contact_id"])

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_tasks_contact_id", "tasks", ["contact_id"])

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("workspace_id", "name", name="uq_tag_workspace_name"),
    )

    op.create_table(
        "lead_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False,
        ),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("contact_id", "tag_id", name="uq_lead_tag_contact_tag"),
    )


def downgrade() -> None:
    op.drop_table("lead_tags")
    op.drop_table("tags")
    op.drop_table("tasks")
    op.drop_table("notes")
    op.drop_index("ix_contacts_workspace_status", table_name="contacts")
    op.drop_column("contacts", "status")
    lead_status.drop(op.get_bind(), checkfirst=True)
