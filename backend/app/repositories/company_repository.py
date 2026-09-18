import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company, CompanySource


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: uuid.UUID, company_id: uuid.UUID) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.id == company_id, Company.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def find_by_domain(self, workspace_id: uuid.UUID, domain: str) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.workspace_id == workspace_id, Company.domain == domain)
        )
        return result.scalars().first()

    async def find_by_normalized_name_and_location(
        self, workspace_id: uuid.UUID, normalized_name: str, city: str | None, state: str | None
    ) -> Company | None:
        stmt = select(Company).where(
            Company.workspace_id == workspace_id,
            Company.normalized_name == normalized_name,
        )
        if city:
            stmt = stmt.where(Company.city == city)
        if state:
            stmt = stmt.where(Company.state == state)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def find_by_phone(self, workspace_id: uuid.UUID, phone: str) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.workspace_id == workspace_id, Company.phone == phone)
        )
        return result.scalars().first()

    async def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Company]:
        stmt = select(Company).where(Company.workspace_id == workspace_id)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(Company.name.ilike(pattern), Company.domain.ilike(pattern))
            )
        stmt = stmt.order_by(Company.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_sources(
        self, workspace_id: uuid.UUID, company_id: uuid.UUID
    ) -> list[CompanySource]:
        result = await self.session.execute(
            select(CompanySource)
            .join(Company, Company.id == CompanySource.company_id)
            .where(Company.workspace_id == workspace_id, CompanySource.company_id == company_id)
            .order_by(CompanySource.retrieved_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, *, workspace_id: uuid.UUID, **fields: Any) -> Company:
        company = Company(workspace_id=workspace_id, **fields)
        self.session.add(company)
        await self.session.flush()  # assigns company.id before it's referenced by a source row
        return company

    def add_source(
        self,
        *,
        company: Company,
        provider: str,
        external_id: str | None,
        source_url: str | None,
        source_type: str,
        raw_reference: dict[str, Any],
    ) -> CompanySource:
        source = CompanySource(
            company_id=company.id,
            provider=provider,
            external_id=external_id,
            source_url=source_url,
            source_type=source_type,
            raw_reference=raw_reference,
        )
        self.session.add(source)
        return source
