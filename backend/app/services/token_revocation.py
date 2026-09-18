"""Server-side JWT revocation (Phase 14).

JWTs are stateless by design, so "logging out" previously did nothing
server-side (see README §16, prior gap). Every access/refresh token now
carries a unique `jti`; revoking one records that `jti` here until its
original expiry, after which the record is dropped automatically — never
grown unbounded.
"""
from typing import Protocol

import redis.asyncio as redis

from app.core.config import get_settings

_KEY_PREFIX = "revoked_jti:"


class TokenRevocationStore(Protocol):
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...


class RedisTokenRevocationStore:
    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        await self._client.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._client.exists(f"{_KEY_PREFIX}{jti}"))


_settings = get_settings()
_redis_client = redis.from_url(_settings.REDIS_URL, decode_responses=True)
_store: TokenRevocationStore = RedisTokenRevocationStore(_redis_client)


async def get_token_revocation_store() -> TokenRevocationStore:
    return _store
