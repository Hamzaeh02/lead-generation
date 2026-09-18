"""Placeholder task proving the Celery worker/beat pipeline is wired up.

Real discovery/enrichment/verification/campaign tasks are added in later
phases (see PHASE 4+ in the project README).
"""
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.ping")
def ping() -> str:
    logger.info("celery_ping")
    return "pong"
