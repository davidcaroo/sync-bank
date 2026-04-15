from __future__ import annotations

from uuid import uuid4

from repositories.db_utils import execute_with_retry
from services.supabase_service import supabase
from services.timezone_service import now_bogota

ACTIVE_JOB_STATUSES = ["queued", "running"]
TERMINAL_JOB_STATUSES = ["success", "failed"]


def create_or_get_job(*, job_type: str, factura_id: str, payload: dict | None = None) -> dict:
    active_res = execute_with_retry(
        lambda: supabase.table("job_tasks")
        .select("*")
        .eq("job_type", job_type)
        .eq("factura_id", factura_id)
        .in_("status", ACTIVE_JOB_STATUSES)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    active_rows = active_res.data or []
    if active_rows:
        active_job = active_rows[0]
        active_job["created"] = False
        return active_job

    job_id = str(uuid4())
    now_iso = now_bogota().isoformat()
    row = {
        "id": job_id,
        "job_type": job_type,
        "factura_id": factura_id,
        "status": "queued",
        "payload": payload or {},
        "result": None,
        "error": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "started_at": None,
        "finished_at": None,
    }

    insert_res = execute_with_retry(lambda: supabase.table("job_tasks").insert(row).execute())
    rows = insert_res.data or []
    created = rows[0] if rows else row
    created["created"] = True
    return created


def get_job(job_id: str) -> dict | None:
    if not job_id:
        return None
    res = execute_with_retry(
        lambda: supabase.table("job_tasks").select("*").eq("id", job_id).limit(1).execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def mark_job_running(job_id: str) -> dict | None:
    now_iso = now_bogota().isoformat()
    res = execute_with_retry(
        lambda: supabase.table("job_tasks")
        .update(
            {
                "status": "running",
                "started_at": now_iso,
                "updated_at": now_iso,
                "error": None,
            }
        )
        .eq("id", job_id)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def mark_job_success(job_id: str, result: dict | None = None) -> dict | None:
    now_iso = now_bogota().isoformat()
    res = execute_with_retry(
        lambda: supabase.table("job_tasks")
        .update(
            {
                "status": "success",
                "result": result or {},
                "error": None,
                "finished_at": now_iso,
                "updated_at": now_iso,
            }
        )
        .eq("id", job_id)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def mark_job_failed(job_id: str, error: str) -> dict | None:
    now_iso = now_bogota().isoformat()
    res = execute_with_retry(
        lambda: supabase.table("job_tasks")
        .update(
            {
                "status": "failed",
                "error": error[:4000],
                "finished_at": now_iso,
                "updated_at": now_iso,
            }
        )
        .eq("id", job_id)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None
