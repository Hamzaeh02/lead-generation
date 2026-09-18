"""companies, contacts, provenance, provider registry

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(
    "company_discovery",
    "person_discovery",
    "local_business_discovery",
    "website_discovery",
    "enrichment",
    "email_finder",
    "email_verifier",
    "social_signal",
    "intent",
    "ai",
    "email_sender",
    name="provider_category",
    create_type=False,
)

_TIMESTAMP_COLS = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)


def upgrade() -> None:
    provider_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("normalized_name", sa.String(500), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("website", sa.String(1000), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("state", sa.String(255), nullable=True),
        sa.Column("country", sa.String(255), nullable=True),
        sa.Column("postal_code", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.String(1000), nullable=True),
        sa.Column("social_urls", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("field_provenance", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_companies_workspace_domain", "companies", ["workspace_id", "domain"])
    op.create_index(
        "ix_companies_workspace_normalized_name", "companies", ["workspace_id", "normalized_name"]
    )

    op.create_table(
        "company_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="api"),
        sa.Column("raw_reference", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_company_sources_company_id", "company_sources", ["company_id"])

    op.create_table(
        "contacts",
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
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(500), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("seniority", sa.String(100), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(1000), nullable=True),
        sa.Column("field_provenance", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_contacts_workspace_email", "contacts", ["workspace_id", "email"])
    op.create_index("ix_contacts_workspace_company", "contacts", ["workspace_id", "company_id"])

    op.create_table(
        "contact_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="api"),
        sa.Column("raw_reference", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_TIMESTAMP_COLS,
    )
    op.create_index("ix_contact_sources_contact_id", "contact_sources", ["contact_id"])

    op.create_table(
        "provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("category", provider_category, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        *_TIMESTAMP_COLS,
        sa.UniqueConstraint("provider", "category", name="uq_provider_category"),
    )

    provider_configs = sa.table(
        "provider_configs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("provider", sa.String),
        sa.column("category", provider_category),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
    )
    import uuid as _uuid

    seed_rows = [
        ("apollo", "company_discovery", 1),
        ("apollo", "person_discovery", 1),
        ("people_data_labs", "company_discovery", 2),
        ("people_data_labs", "person_discovery", 2),
        ("serpapi", "local_business_discovery", 1),
        ("apify", "local_business_discovery", 2),
        ("phantombuster", "social_signal", 1),
        ("hunter", "email_finder", 1),
        ("hunter", "email_verifier", 1),
        ("openai", "ai", 1),
        ("smtp", "email_sender", 1),
    ]
    op.bulk_insert(
        provider_configs,
        [
            {
                "id": _uuid.uuid4(),
                "provider": provider,
                "category": category,
                "enabled": False,
                "priority": priority,
            }
            for provider, category, priority in seed_rows
        ],
    )


def downgrade() -> None:
    op.drop_table("provider_configs")
    op.drop_table("contact_sources")
    op.drop_table("contacts")
    op.drop_table("company_sources")
    op.drop_table("companies")
    provider_category.drop(op.get_bind(), checkfirst=True)
