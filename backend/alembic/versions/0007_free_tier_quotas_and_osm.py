"""monthly_free_quota column + OpenStreetMap registry row + known free quotas

Free-tier numbers below were verified via web search on 2026-08-08 and are
approximate/subject to change — see README §"Free-tier plan" for sources
and caveats (Apollo's free-plan API access in particular is uncertain).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-08

"""
import uuid as uuid_module
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

provider_category = postgresql.ENUM(name="provider_category", create_type=False)

_QUOTAS = {
    ("apollo", "company_discovery"): 100,
    ("apollo", "person_discovery"): 100,
    ("people_data_labs", "company_discovery"): 100,
    ("people_data_labs", "person_discovery"): 100,
    ("people_data_labs", "enrichment"): 100,
    ("serpapi", "local_business_discovery"): 250,
    ("hunter", "email_finder"): 25,
    ("hunter", "email_verifier"): 50,
    # apify (usage-based $5/mo credit, not a call count) and phantombuster
    # (time-based execution minutes) are left null — a count-based quota
    # doesn't fit how their free tiers actually work.
}


def upgrade() -> None:
    op.add_column("provider_configs", sa.Column("monthly_free_quota", sa.Integer(), nullable=True))

    provider_configs = sa.table(
        "provider_configs",
        sa.column("provider", sa.String),
        sa.column("category", provider_category),
        sa.column("monthly_free_quota", sa.Integer),
    )
    for (provider, category), quota in _QUOTAS.items():
        op.execute(
            provider_configs.update()
            .where(provider_configs.c.provider == provider, provider_configs.c.category == category)
            .values(monthly_free_quota=quota)
        )

    # OpenStreetMap needs no credentials at all, so — unlike every other
    # provider here — it's seeded enabled by default.
    op.bulk_insert(
        sa.table(
            "provider_configs",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("provider", sa.String),
            sa.column("category", provider_category),
            sa.column("enabled", sa.Boolean),
            sa.column("priority", sa.Integer),
        ),
        [
            {
                "id": uuid_module.uuid4(),
                "provider": "openstreetmap",
                "category": "local_business_discovery",
                "enabled": True,
                "priority": 3,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM provider_configs WHERE provider = 'openstreetmap' AND category = 'local_business_discovery'"
    )
    op.drop_column("provider_configs", "monthly_free_quota")
