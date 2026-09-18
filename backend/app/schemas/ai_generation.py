import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AIGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    provider: str
    model: str
    prompt_version: str
    source_fields_used: list[str]
    subject: str | None
    opening_line: str | None
    body: str | None
    cta: str | None
    outreach_angle: str | None
    personalization_source: str | None
    signal_id: uuid.UUID | None
    source_url: str | None
    generated_at: datetime
