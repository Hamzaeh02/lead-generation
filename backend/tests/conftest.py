import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.core.database import Base
from app.main import app
from app.services.rate_limiter import get_rate_limiter
from app.services.token_revocation import get_token_revocation_store


class _FakeTokenRevocationStore:
    """In-memory stand-in for Redis, scoped to a single test — no real
    Redis server is available/desired in the test environment (see
    conftest's db_session for the same rationale re: Postgres)."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        self._revoked.add(jti)

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked


class _AlwaysAllowRateLimiter:
    """Real rate limiting is verified against a real (tiny-limit) fake in
    tests/test_rate_limiting.py; every other test needs auth endpoints to
    never 429 regardless of how many times a test calls register/login."""

    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        return True


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db_session():
        yield db_session

    fake_revocation_store = _FakeTokenRevocationStore()

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_token_revocation_store] = lambda: fake_revocation_store
    app.dependency_overrides[get_rate_limiter] = lambda: _AlwaysAllowRateLimiter()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"
