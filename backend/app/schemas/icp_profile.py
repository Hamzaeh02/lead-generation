import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ICPProfileBase(BaseModel):
    name: str
    industry: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    employee_count_min: int | None = Field(default=None, ge=0)
    employee_count_max: int | None = Field(default=None, ge=0)
    target_titles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    weights: dict[str, Any] = Field(default_factory=dict)


class ICPProfileCreate(ICPProfileBase):
    pass


class ICPProfileUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    target_titles: list[str] | None = None
    keywords: list[str] | None = None
    weights: dict[str, Any] | None = None


class ICPProfileRead(ICPProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class ICPScoreRead(BaseModel):
    company_id: uuid.UUID
    icp_profile_id: uuid.UUID
    score: int
    matched_criteria: list[str]


class NLICPParseRequest(BaseModel):
    text: str


class NLICPParseResponse(BaseModel):
    """Structured criteria suggested from free-text input, for the user to
    review/edit before saving as an ICPProfile or running a search — never
    executed or persisted automatically."""

    suggested: ICPProfileBase
    unparsed_hints: list[str]
