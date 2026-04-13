from fastapi import APIRouter, Query
from repositories.logs_repository import list_logs_paginated
from repositories.db_utils import run_in_executor

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    estado: str | None = None,
):
    res = await run_in_executor(lambda: list_logs_paginated(page=page, page_size=page_size, estado=estado))
    return {
        "data": res.data or [],
        "count": res.count or 0,
        "page": page,
        "page_size": page_size,
    }
