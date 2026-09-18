from pydantic import BaseModel, Field

#: CSV column -> canonical field. Users map their file's headers to these.
IMPORTABLE_FIELDS = (
    "company",
    "website",
    "email",
    "first_name",
    "last_name",
    "job_title",
    "phone",
    "city",
    "state",
    "country",
    "industry",
)


class ImportPreviewRow(BaseModel):
    row_number: int
    values: dict[str, str]


class ImportPreviewResponse(BaseModel):
    headers: list[str]
    suggested_mapping: dict[str, str]  # canonical field -> detected CSV header
    sample_rows: list[ImportPreviewRow]
    total_rows: int


class ImportMapping(BaseModel):
    """canonical field -> CSV header name, e.g. {"company": "Company Name"}."""

    mapping: dict[str, str] = Field(default_factory=dict)


class ImportRowError(BaseModel):
    row_number: int
    reason: str


class ImportResultResponse(BaseModel):
    total_rows: int
    companies_created: int
    companies_matched: int
    contacts_created: int
    contacts_matched: int
    skipped_invalid: int
    errors: list[ImportRowError]
