from fastapi import APIRouter, Query
from services.supabase_service import supabase

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    estado: str | None = None,
):
    query = supabase.table("logs_email").select("*", count="exact")
    if estado:
        query = query.eq("estado", estado)

    start = (page - 1) * page_size
    end = start + page_size - 1

    res = query.order("created_at", desc=True).range(start, end).execute()
    return {
        "data": res.data or [],
        "count": res.count or 0,
        "page": page,
        "page_size": page_size,
    }
