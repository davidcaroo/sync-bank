from services.supabase_service import supabase
from repositories.db_utils import execute_with_retry


def list_logs_paginated(*, page: int, page_size: int, estado: str | None = None):
    query = supabase.table("logs_email").select("*", count="exact")
    if estado:
        query = query.eq("estado", estado)

    start = (page - 1) * page_size
    end = start + page_size - 1

    return execute_with_retry(lambda: query.order("created_at", desc=True).range(start, end).execute())
