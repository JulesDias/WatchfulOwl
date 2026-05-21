import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.processing.pipeline import run_collection_cycle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_collection() -> None:
    try:
        await run_collection_cycle()
    except Exception:
        logger.exception("Scheduled collection failed")


def start_scheduler() -> None:
    settings = get_settings()
    if scheduler.running:
        return
    if settings.collection_interval_minutes <= 0:
        logger.info("Scheduler disabled: COLLECTION_INTERVAL_MINUTES <= 0")
        return
    scheduler.add_job(
        scheduled_collection,
        trigger="interval",
        minutes=settings.collection_interval_minutes,
        id="collection_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started with interval=%s minutes",
        settings.collection_interval_minutes,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
