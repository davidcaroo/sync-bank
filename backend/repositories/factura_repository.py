from services.supabase_service import supabase
from repositories.db_utils import execute_with_retry


def _is_unique_violation(exc: Exception) -> bool:
    text = str(exc).lower()
    return "duplicate key" in text or "unique" in text or "23505" in text


def find_factura_by_cufe(cufe: str | None):
    if not cufe:
        return None
    res = execute_with_retry(lambda: supabase.table("facturas").select("*").eq("cufe", cufe).limit(1).execute())
    return res.data[0] if res.data else None


def get_successful_causacion(factura_id: str):
    res = execute_with_retry(
        lambda: supabase.table("causaciones")
        .select("alegra_bill_id, estado, created_at")
        .eq("factura_id", factura_id)
        .eq("estado", "exitoso")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def mark_factura_estado(factura_id: str, estado: str):
    execute_with_retry(lambda: supabase.table("facturas").update({"estado": estado}).eq("id", factura_id).execute())


def save_factura(factura_data: dict, items: list):
    cufe = factura_data.get("cufe")
    existing = find_factura_by_cufe(cufe)
    if existing:
        current_status = existing.get("estado")
        if current_status not in {"procesado", "duplicado"}:
            mark_factura_estado(existing["id"], "duplicado")
        return {"factura_id": existing["id"], "duplicado": True}

    # Insert factura
    try:
        factura_res = execute_with_retry(lambda: supabase.table("facturas").insert(factura_data).execute())
    except Exception as exc:
        if cufe and _is_unique_violation(exc):
            existing = find_factura_by_cufe(cufe)
            if existing:
                current_status = existing.get("estado")
                if current_status not in {"procesado", "duplicado"}:
                    mark_factura_estado(existing["id"], "duplicado")
                return {"factura_id": existing["id"], "duplicado": True}
        raise

    if not factura_res.data:
        return {"factura_id": None, "duplicado": False}

    factura_id = factura_res.data[0]["id"]

    # Insert items
    for item in items:
        item["factura_id"] = factura_id

    execute_with_retry(lambda: supabase.table("items_factura").insert(items).execute())
    return {"factura_id": factura_id, "duplicado": False}


def get_facturas_stats():
    res = execute_with_retry(lambda: supabase.table("facturas").select("estado, created_at").execute())
    return res.data or []


def get_facturas_paginated(
    *,
    page: int,
    page_size: int,
    estado: str | None = None,
    proveedor: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
):
    query = supabase.table("facturas").select("*, items_factura(*)", count="exact")
    if estado:
        query = query.eq("estado", estado)
    if proveedor:
        query = query.ilike("nombre_proveedor", f"%{proveedor}%")
    if desde:
        query = query.gte("fecha_emision", desde)
    if hasta:
        query = query.lte("fecha_emision", hasta)

    start = (page - 1) * page_size
    end = start + page_size - 1
    res = execute_with_retry(lambda: query.order("created_at", desc=True).range(start, end).execute())
    return res


def get_factura_with_items(factura_id: str):
    res = execute_with_retry(lambda: supabase.table("facturas").select("*, items_factura(*)").eq("id", factura_id).single().execute())
    return res.data if res else None


def update_factura_fields(factura_id: str, payload: dict):
    res = execute_with_retry(lambda: supabase.table("facturas").update(payload).eq("id", factura_id).execute())
    return res.data[0] if res.data else None


def update_item_fields(item_id: str, payload: dict):
    res = execute_with_retry(lambda: supabase.table("items_factura").update(payload).eq("id", item_id).execute())
    return res.data[0] if res.data else None


def list_provider_nits():
    res = execute_with_retry(lambda: supabase.table("facturas").select("nit_proveedor").execute())
    rows = res.data or []
    return sorted({(r.get("nit_proveedor") or "").strip() for r in rows if r.get("nit_proveedor")})


def list_factura_items_by_nit(nit_proveedor: str):
    res = execute_with_retry(
        lambda: supabase.table("facturas")
        .select("id, items_factura(cuenta_contable_alegra)")
        .eq("nit_proveedor", nit_proveedor)
        .execute()
    )
    return res.data or []
