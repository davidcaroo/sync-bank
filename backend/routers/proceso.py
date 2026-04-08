from fastapi import APIRouter
from services.email_service import check_emails
from datetime import datetime

router = APIRouter(prefix="/proceso", tags=["proceso"])

last_run = None

@router.post("/manual")
async def trigger_manual():
    global last_run
    await check_emails()
    last_run = datetime.now()
    return {"status": "success", "timestamp": last_run}

@router.get("/status")
async def get_status():
    return {"last_execution": last_run}
