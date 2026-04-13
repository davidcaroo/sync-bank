import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.email_service import check_emails
from services.provider_mapping_service import provider_mapping_service

scheduler = AsyncIOScheduler()
logger = logging.getLogger("scheduler")
_mapping_lock = asyncio.Lock()
_mapping_cursor = 0

_BATCH_SIZE = 100
_MAX_CONCURRENCY = 5

def start_scheduler():
    scheduler.add_job(check_emails, 'interval', minutes=5)
    # Recompute provider->account mappings every 6 hours
    try:
        scheduler.add_job(_recompute_mappings_job, 'interval', hours=6, max_instances=1, coalesce=True, misfire_grace_time=300)
    except Exception:
        # Fallback: ignore scheduler job registration failures
        pass
    scheduler.start()


async def _recompute_mappings_job():
    global _mapping_cursor

    if _mapping_lock.locked():
        logger.warning("recompute_mappings_skipped")
        return

    async with _mapping_lock:
        try:
            result = await provider_mapping_service.recompute_all_mappings(
                start_index=_mapping_cursor,
                batch_size=_BATCH_SIZE,
                max_concurrency=_MAX_CONCURRENCY,
            )
            _mapping_cursor = result.get("next_index", 0)
            logger.info("recompute_mappings_done", extra={
                "batch_size": result.get("batch_size"),
                "total": result.get("total"),
                "next_index": _mapping_cursor,
            })
        except Exception as exc:
            logger.error("recompute_mappings_failed", extra={"error": str(exc)})
