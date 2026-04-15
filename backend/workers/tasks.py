from __future__ import annotations

import asyncio
import logging
import time

import dramatiq

from config import settings
from observability.metrics import JOB_EXECUTION_DURATION_SECONDS, JOB_TRANSITIONS, WORKER_IN_PROGRESS
from observability.telemetry import get_tracer
from repositories.job_repository import mark_job_failed, mark_job_running, mark_job_success
from workers.broker import redis_broker  # noqa: F401

logger = logging.getLogger("workers")
tracer = get_tracer("syncbank.workers")


@dramatiq.actor(
    queue_name=settings.JOB_QUEUE_NAME,
    max_retries=3,
    min_backoff=5_000,
    max_backoff=60_000,
    time_limit=10 * 60 * 1000,
)
def causar_factura_job(job_id: str, factura_id: str, overrides_map: dict | None = None) -> None:
    from services.factura_service import factura_service

    start = time.perf_counter()
    WORKER_IN_PROGRESS.labels(job_type="causar_factura").inc()
    JOB_TRANSITIONS.labels(job_type="causar_factura", status="running").inc()
    mark_job_running(job_id)

    span_cm = tracer.start_as_current_span("worker.causar_factura_job") if tracer else None
    if span_cm:
        span_cm.__enter__()

    try:
        logger.info("job_started", extra={"job_id": job_id, "factura_id": factura_id})
        result = asyncio.run(factura_service.causar_factura(factura_id, overrides_map or {}))
        payload = result if isinstance(result, dict) else {"message": str(result)}
        mark_job_success(job_id, payload)
        JOB_TRANSITIONS.labels(job_type="causar_factura", status="success").inc()
        JOB_EXECUTION_DURATION_SECONDS.labels(job_type="causar_factura", status="success").observe(
            time.perf_counter() - start
        )
        logger.info("job_completed", extra={"job_id": job_id, "factura_id": factura_id})
    except Exception as exc:
        logger.exception("causar_factura_job_failed", extra={"job_id": job_id, "factura_id": factura_id})
        mark_job_failed(job_id, str(exc))
        JOB_TRANSITIONS.labels(job_type="causar_factura", status="failed").inc()
        JOB_EXECUTION_DURATION_SECONDS.labels(job_type="causar_factura", status="failed").observe(
            time.perf_counter() - start
        )
        raise
    finally:
        WORKER_IN_PROGRESS.labels(job_type="causar_factura").dec()
        if span_cm:
            span_cm.__exit__(None, None, None)
