from fastapi import APIRouter
from services.email_service import check_emails
from services.timezone_service import now_bogota

router = APIRouter(prefix="/proceso", tags=["proceso"])

last_run = None
last_summary = None

@router.post("/manual")
async def trigger_manual():
    global last_run, last_summary
    summary = await check_emails(search_criteria='ALL')
    last_run = now_bogota()
    last_summary = summary or {}

    created = int((summary or {}).get("created") or 0)
    duplicates = int((summary or {}).get("duplicates") or 0)
    invalid = int((summary or {}).get("invalid") or 0)
    errors = int((summary or {}).get("errors") or 0)

    status = "success"
    if errors > 0:
        status = "partial"
    if created == 0 and duplicates == 0 and invalid == 0 and errors == 0:
        status = "noop"

    return {
        "status": status,
        "timestamp": last_run,
        "summary": last_summary,
    }

@router.get("/status")
async def get_status():
    return {
        "last_execution": last_run,
        "summary": last_summary or {},
    }
