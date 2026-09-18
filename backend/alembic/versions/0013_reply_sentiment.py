"""email_events.reply_sentiment (AI-classified reply sentiment for
"positive replies" reporting).

Nullable, no default: null means "not classified" — either the event
isn't a reply, the webhook payload carried no extractable reply text, or
no AI provider was enabled/configured at ingestion time. Never guessed;
only ever set by an actual Groq/OpenAI classification call on real reply
text (see app/services/reply_sentiment_service.py).

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

reply_sentiment = postgresql.ENUM(
    "positive", "neutral", "negative",
    name="reply_sentiment", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    reply_sentiment.create(bind, checkfirst=True)
    op.add_column(
        "email_events",
        sa.Column("reply_sentiment", reply_sentiment, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_events", "reply_sentiment")
    reply_sentiment.drop(op.get_bind(), checkfirst=True)
