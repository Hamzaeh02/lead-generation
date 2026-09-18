"""Periodic campaign processing (section 43: "Use Celery" for scheduling).

Runs on a Celery beat schedule, sweeps every RUNNING campaign across all
workspaces, and processes due sends for each via the same
CampaignSendingService the manual `/campaigns/{id}/process` endpoint uses
— one code path for both, no duplicated sending logic.
"""
from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.repositories.campaign_repository import CampaignRepository
from app.services.campaign_sending_service import CampaignSendingService
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _process_all_running_campaigns() -> dict:
    settings = get_settings()
    results = {"campaigns_processed": 0, "sent": 0, "failed": 0}

    async with AsyncSessionLocal() as session:
        campaigns = await CampaignRepository(session).list_all_running()
        service = CampaignSendingService(session, settings)

        for campaign in campaigns:
            try:
                summary = await service.process_campaign(
                    workspace_id=campaign.workspace_id, campaign_id=campaign.id
                )
            except Exception as exc:  # noqa: BLE001 — one campaign's error shouldn't stop the sweep
                logger.warning(
                    "campaign_processing_failed", campaign_id=str(campaign.id), error=str(exc)
                )
                continue

            results["campaigns_processed"] += 1
            results["sent"] += summary["sent"]
            results["failed"] += summary["failed"]

    return results


@celery_app.task(name="app.tasks.process_due_campaign_sends")
def process_due_campaign_sends() -> dict:
    return asyncio.run(_process_all_running_campaigns())
