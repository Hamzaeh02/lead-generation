import pytest

from app.main import app
from app.services.rate_limiter import get_rate_limiter

pytestmark = pytest.mark.asyncio


class _TinyLimitRateLimiter:
    """Real fixed-window logic (unlike conftest's always-allow fake) but
    with a limit low enough to trip deterministically in a couple of calls."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._counts: dict[str, int] = {}

    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] <= self._limit


async def test_login_rate_limit_returns_429_after_threshold(client, unique_email):
    limiter = _TinyLimitRateLimiter(limit=2)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        payload = {"email": unique_email, "password": "wrong-password"}
        first = await client.post("/api/v1/auth/login", json=payload)
        second = await client.post("/api/v1/auth/login", json=payload)
        third = await client.post("/api/v1/auth/login", json=payload)

        assert first.status_code == 401
        assert second.status_code == 401
        assert third.status_code == 429
    finally:
        del app.dependency_overrides[get_rate_limiter]


async def test_rate_limit_is_scoped_by_endpoint_not_shared_globally(client, unique_email):
    limiter = _TinyLimitRateLimiter(limit=1)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        login_payload = {"email": unique_email, "password": "wrong-password"}
        await client.post("/api/v1/auth/login", json=login_payload)
        blocked_login = await client.post("/api/v1/auth/login", json=login_payload)
        assert blocked_login.status_code == 429

        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "S3curePassw0rd!",
                "full_name": "Test User",
                "workspace_name": "Acme Inc",
            },
        )
        assert register_response.status_code == 201
    finally:
        del app.dependency_overrides[get_rate_limiter]
