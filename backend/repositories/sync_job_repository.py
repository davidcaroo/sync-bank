from typing import Any

from psycopg.types.json import Jsonb

from repositories.database import connection, transaction

JOB_TYPE = "email_sync"
ACTIVE = "('pending', 'running')"


def _active(conn) -> dict[str, Any] | None:
    return conn.execute(
        f"select * from sync_jobs where job_type = %s and status in {ACTIVE}",
        (JOB_TYPE,),
    ).fetchone()


def enqueue_email_sync(requested_by: str) -> dict[str, Any]:
    """Create the email sync job, or return the one already active."""
    with transaction() as conn:
        row = conn.execute(
            f"""
            insert into sync_jobs (job_type, requested_by) values (%s, %s)
            on conflict (job_type) where status in {ACTIVE} do nothing
            returning *
            """,
            (JOB_TYPE, requested_by),
        ).fetchone()
        if row:
            return {"job": row, "created": True}
        return {"job": _active(conn), "created": False}


def claim_next_email_sync() -> dict[str, Any] | None:
    with transaction() as conn:
        return conn.execute(
            """
            update sync_jobs set status = 'running', attempts = attempts + 1,
                started_at = now(), updated_at = now()
            where id = (
                select id from sync_jobs
                where job_type = %s and status = 'pending'
                order by created_at limit 1
                for update skip locked
            )
            returning *
            """,
            (JOB_TYPE,),
        ).fetchone()


def update_progress(job_id, progress: dict) -> None:
    with transaction() as conn:
        conn.execute(
            "update sync_jobs set progress = %s, updated_at = now() where id = %s",
            (Jsonb(progress), job_id),
        )


def finish_job(job_id, result: dict) -> None:
    with transaction() as conn:
        conn.execute(
            """
            update sync_jobs set status = 'succeeded', result = %s,
                error_message = null, finished_at = now(), updated_at = now()
            where id = %s
            """,
            (Jsonb(result), job_id),
        )


def retry_or_fail_job(job_id, error: str) -> str:
    """Back to the queue while attempts remain; otherwise failed. Returns the new status."""
    with transaction() as conn:
        row = conn.execute(
            """
            update sync_jobs set error_message = %s, updated_at = now(),
                status = case when attempts < max_attempts then 'pending' else 'failed' end,
                finished_at = case when attempts < max_attempts then null else now() end
            where id = %s returning status
            """,
            (error, job_id),
        ).fetchone()
    return row["status"]


def recover_interrupted_jobs(stale_seconds: int = 300) -> int:
    """Jobs 'running' with no heartbeat (progress write) for `stale_seconds`, i.e. left
    behind by a restart: requeue them or fail them if out of attempts. A job that a
    live instance is still working on keeps updating updated_at and is left alone."""
    with transaction() as conn:
        rows = conn.execute(
            """
            update sync_jobs set updated_at = now(),
                status = case when attempts < max_attempts then 'pending' else 'failed' end,
                finished_at = case when attempts < max_attempts then null else now() end,
                error_message = 'Trabajo interrumpido por un reinicio del servicio'
            where job_type = %s and status = 'running'
              and updated_at < now() - make_interval(secs => %s)
            returning id
            """,
            (JOB_TYPE, stale_seconds),
        ).fetchall()
    return len(rows)


def get_sync_status() -> dict[str, Any] | None:
    """The active job, else the most recent one."""
    with connection() as conn:
        return _active(conn) or conn.execute(
            "select * from sync_jobs where job_type = %s order by created_at desc limit 1",
            (JOB_TYPE,),
        ).fetchone()
