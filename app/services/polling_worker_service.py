import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.redis import redis_client
from app.database.session import AsyncSessionLocal
from app.models.polling_jobs import PollingJob, SuccessCriteria
from app.services.price_service import PriceService
from app.services.providers.registry import get_provider

logger = logging.getLogger(__name__)

# How often the worker wakes up to check for due jobs (seconds)
WORKER_TICK_INTERVAL = 10


async def polling_worker():
    """
    Background task started at app startup (see main.py lifespan).

    Wakes every WORKER_TICK_INTERVAL seconds and checks all non-failed
    PollingJobs. For each due job, builds a PriceService with the job's
    configured provider and delegates the full fetch pipeline to it.
    """
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PollingJob).where(PollingJob.status != SuccessCriteria.failed)
                )
                active_jobs = result.scalars().all()

                now = datetime.now(timezone.utc)

                for job in active_jobs:
                    # Fall back to epoch so a brand-new job is always due immediately
                    last_polled = job.last_polled_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
                    due_at = last_polled + timedelta(seconds=job.interval)

                    if now < due_at:
                        continue

                    logger.info(f"[{job.symbol}] Polling due (interval={job.interval}s)")
                    try:
                        service = PriceService(
                            provider=get_provider(job.provider),
                            db=db,
                            cache=redis_client,
                        )
                        await service.get_latest_price(job.symbol, publish_to_kafka=True)

                        job.status = SuccessCriteria.success
                        job.last_polled_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.info(f"[{job.symbol}] Poll succeeded")

                    except Exception as e:
                        logger.error(f"[{job.symbol}] Poll failed: {e}")
                        job.status = SuccessCriteria.failed
                        await db.commit()

        except Exception as e:
            logger.error(f"[polling_worker] Unexpected error: {e}")

        await asyncio.sleep(WORKER_TICK_INTERVAL)
