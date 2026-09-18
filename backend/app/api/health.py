import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.utils.logging import get_logger
from app.utils.metrics import render_metrics

router = APIRouter(tags=["health"])
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health")
async def health():
    """Liveness probe: process is up. No dependency checks."""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint. Unauthenticated, like most metrics
    endpoints — restrict access at the reverse-proxy/network level in
    production (see README §16), not with app-level auth that a scraper
    can't easily present anyway."""
    return render_metrics()


@router.get("/ready")
async def ready():
    """Readiness probe: checks database and Redis connectivity."""
    checks: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="database", error=str(exc))
        checks["database"] = "unavailable"

    try:
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="redis", error=str(exc))
        checks["redis"] = "unavailable"

    overall_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if overall_ok else "degraded", "checks": checks}
