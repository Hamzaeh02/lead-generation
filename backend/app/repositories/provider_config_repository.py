import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_config import ProviderConfig
from app.providers.base import ProviderCategory


class ProviderConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[ProviderConfig]:
        result = await self.session.execute(
            select(ProviderConfig).order_by(ProviderConfig.category, ProviderConfig.priority)
        )
        return list(result.scalars().all())

    async def list_enabled_for_category(
        self, category: ProviderCategory
    ) -> list[ProviderConfig]:
        result = await self.session.execute(
            select(ProviderConfig)
            .where(ProviderConfig.category == category, ProviderConfig.enabled.is_(True))
            .order_by(ProviderConfig.priority)
        )
        return list(result.scalars().all())

    async def get_by_id(self, provider_config_id: uuid.UUID) -> ProviderConfig | None:
        return await self.session.get(ProviderConfig, provider_config_id)

    async def get_by_provider_and_category(
        self, provider: str, category: ProviderCategory
    ) -> ProviderConfig | None:
        result = await self.session.execute(
            select(ProviderConfig).where(
                ProviderConfig.provider == provider, ProviderConfig.category == category
            )
        )
        return result.scalar_one_or_none()
