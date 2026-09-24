import asyncio
import logging
from datetime import date

from config import settings
from repositories import sync_job_repository as repo
from repositories.db_utils import run_in_executor
from services.email_service import check_emails

logger = logging.getLogger("sync_jobs")

RETRY_DELAY_SECONDS = 30
POLL_SECONDS = 30
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_wakeup: asyncio.Event | None = None
_runner: asyncio.Task | None = None


def _criteria(requested_by: str) -> str:
    """Manual runs rescan everything received since the minimum issue date (catches
    mails a person already opened); scheduled runs only read unseen mail."""
    if requested_by == "manual":
        since = date.fromisoformat(settings.MIN_ISSUE_DATE)
        return f"SINCE {since.day:02d}-{_MONTHS[since.month - 1]}-{since.year}"
    return "UNSEEN"


async def enqueue(requested_by: str) -> dict:
    result = await run_in_executor(lambda: repo.enqueue_email_sync(requested_by))
    if _wakeup:
        _wakeup.set()
    return result


async def enqueue_scheduled() -> None:
    await enqueue("scheduler")


def current_status() -> dict | None:
    return repo.get_sync_status()


async def _execute(job: dict) -> None:
    async def progress(value: dict) -> None:
        await run_in_executor(lambda: repo.update_progress(job["id"], value))

    error = None
    try:
        summary = await check_emails(_criteria(job["requested_by"]), on_progress=progress)
    except Exception as exc:
        logger.exception("sync_job_crashed", extra={"job_id": str(job["id"])})
        error = str(exc) or repr(exc)
    else:
        error = summary.get("fatal_error")
        if not error:
            await run_in_executor(lambda: repo.finish_job(job["id"], summary))
            return
    status = await run_in_executor(lambda: repo.retry_or_fail_job(job["id"], error))
    if status == "pending":
        await asyncio.sleep(RETRY_DELAY_SECONDS)


async def run_pending() -> None:
    while True:
        job = await run_in_executor(lambda: repo.claim_next_email_sync())
        if not job:
            return
        await _execute(job)


async def recover() -> None:
    count = await run_in_executor(lambda: repo.recover_interrupted_jobs())
    if count:
        logger.warning("sync_jobs_recovered", extra={"job_id": count})


async def _loop() -> None:
    await recover()
    while True:
        try:
            await run_pending()
        except Exception:
            logger.exception("sync_runner_failed")
        try:
            await asyncio.wait_for(_wakeup.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass
        _wakeup.clear()


def start_runner() -> None:
    global _wakeup, _runner
    _wakeup = asyncio.Event()
    _runner = asyncio.create_task(_loop())


def stop_runner() -> None:
    if _runner:
        _runner.cancel()
