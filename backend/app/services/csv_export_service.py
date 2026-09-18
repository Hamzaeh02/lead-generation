"""CSV lead export. Suppression filtering is added once the suppression
system exists (Phase 11) — until then this exports all workspace contacts."""
from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contact_repository import ContactRepository

_EXPORT_COLUMNS = (
    "company",
    "contact_name",
    "job_title",
    "email",
    "phone",
    "website",
    "city",
    "state",
    "country",
    "industry",
    "created_at",
)


class CsvExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contacts = ContactRepository(session)

    async def export(self, *, workspace_id: uuid.UUID) -> str:
        contacts = await self.contacts.list_for_workspace(workspace_id, limit=100_000, offset=0)

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_EXPORT_COLUMNS)
        writer.writeheader()

        for contact in contacts:
            company = contact.company
            writer.writerow(
                {
                    "company": company.name if company else "",
                    "contact_name": contact.full_name or "",
                    "job_title": contact.job_title or "",
                    "email": contact.email or "",
                    "phone": contact.phone or "",
                    "website": company.website if company else "",
                    "city": company.city if company else "",
                    "state": company.state if company else "",
                    "country": company.country if company else "",
                    "industry": company.industry if company else "",
                    "created_at": contact.created_at.isoformat(),
                }
            )

        return buffer.getvalue()
