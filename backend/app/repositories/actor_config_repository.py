import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actor_config import ActorConfig
from app.providers.base import ProviderCategory


class ActorConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[ActorConfig]:
        result = await self.session.execute(
            select(ActorConfig).order_by(ActorConfig.category, ActorConfig.priority)
        )
        return list(result.scalars().all())

    async def get_by_id(self, actor_config_id: uuid.UUID) -> ActorConfig | None:
        return await self.session.get(ActorConfig, actor_config_id)

    async def get_best_for_category(self, category: ProviderCategory) -> ActorConfig | None:
        result = await self.session.execute(
            select(ActorConfig)
            .where(ActorConfig.category == category, ActorConfig.enabled.is_(True))
            .order_by(ActorConfig.priority)
            .limit(1)
        )
        return result.scalars().first()

    def create(self, **fields) -> ActorConfig:
        actor_config = ActorConfig(**fields)
        self.session.add(actor_config)
        return actor_config
