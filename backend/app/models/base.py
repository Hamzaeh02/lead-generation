import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def str_enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """values_callable for every Enum(SomeStrEnum, ...) column in this
    codebase. Without it, SQLAlchemy binds/validates using the enum
    MEMBER NAME ("FREE") rather than its value ("free") — invisible on
    SQLite (no native enum type, just a CHECK constraint using those same
    names) but a hard mismatch against Postgres, where the Alembic
    migrations create native enum types using the lowercase values."""
    return [member.value for member in enum_cls]


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
