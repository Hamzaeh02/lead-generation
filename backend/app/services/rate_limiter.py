"""Redis-backed fixed-window rate limiting (Phase 14).

Applied to auth endpoints (register/login/refresh) to slow down credential
stuffing / brute-force attempts. Keyed by client IP + endpoint scope, not
by account, so it can't be used to lock a legitimate user out by hammering
their email — the tradeoff is a shared IP (NAT, office network) shares one
budget, which is an acceptable default here, not a general-purpose API
gateway rate limiter.
"""
from typing import Protocol

import redis.asyncio as redis

from app.core.config import get_settings


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Returns True if the call is allowed, False if the limit is exceeded."""
        ...


class RedisRateLimiter:
    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        redis_key = f"ratelimit:{key}"
        current = await self._client.incr(redis_key)
        if current == 1:
            await self._client.expire(redis_key, window_seconds)
        return current <= limit


_settings = get_settings()
_redis_client = redis.from_url(_settings.REDIS_URL, decode_responses=True)
_limiter: RateLimiter = RedisRateLimiter(_redis_client)


async def get_rate_limiter() -> RateLimiter:
    return _limiter
