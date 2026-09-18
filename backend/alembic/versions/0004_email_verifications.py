"""email_verifications

Hunter's provider_configs rows (email_finder, email_verifier) were already
seeded disabled in migration 0002 — this phase makes them usable, no new
registry rows needed.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

verification_status = postgresql.ENUM(
    "valid", "invalid", "risky", "unknown", name="verification_status", create_type=False
)


def upgrade() -> None:
    verification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("verification_status", verification_status, nullable=False),
        sa.Column("verification_score", sa.Integer(), nullable=True),
        sa.Column("mx_records", sa.Boolean(), nullable=True),
        sa.Column("smtp_check", sa.Boolean(), nullable=True),
        sa.Column("accept_all", sa.Boolean(), nullable=True),
        sa.Column("disposable", sa.Boolean(), nullable=True),
        sa.Column("free_provider", sa.Boolean(), nullable=True),
        sa.Column("role_account", sa.Boolean(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_email_verifications_workspace_contact",
        "email_verifications",
        ["workspace_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_table("email_verifications")
    verification_status.drop(op.get_bind(), checkfirst=True)
