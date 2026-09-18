import uuid

from pydantic import BaseModel


class LeadScoreRead(BaseModel):
    contact_id: uuid.UUID
    score: int
    breakdown: list[str]
