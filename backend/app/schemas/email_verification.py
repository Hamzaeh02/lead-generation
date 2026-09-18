import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.providers.email_verifiers.base import VerificationStatus
from app.schemas.contact import ContactRead


class EmailVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    email: str
    provider: str
    verification_status: VerificationStatus
    verification_score: int | None
    mx_records: bool | None
    smtp_check: bool | None
    accept_all: bool | None
    disposable: bool | None
    free_provider: bool | None
    role_account: bool | None
    raw_response: dict[str, Any]
    verified_at: datetime


class FindEmailResponse(BaseModel):
    contact: ContactRead
    email_found: bool
    confidence: str | None = None
