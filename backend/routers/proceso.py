from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from repositories.db_utils import run_in_executor
from services import sync_job_service

router = APIRouter(prefix="/proceso", tags=["proceso"])


@router.post("/manual")
async def trigger_manual():
    """Queues the email sync (or returns the active one) and answers at once."""
    result = await sync_job_service.enqueue("manual")
    return JSONResponse(status_code=202, content=jsonable_encoder(result))


@router.get("/status")
async def get_status():
    job = await run_in_executor(sync_job_service.current_status)
    if not job:
        return {"job": None, "summary": {}, "last_execution": None}
    job = jsonable_encoder(job)
    return {
        "job": job,
        "summary": job.get("result") or {},
        "last_execution": job.get("finished_at") or job.get("started_at"),
    }
