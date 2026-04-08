from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def _is_unique_violation(exc: Exception) -> bool:
    text = str(exc).lower()
    return "duplicate key" in text or "unique" in text or "23505" in text

def get_config_cuenta(nit: str):
    res = (
        supabase.table("config_cuentas")
        .select("*")
        .eq("nit_proveedor", nit)
        .eq("activo", True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def sync_config_proveedor_nombre(nit: str | None, nombre_proveedor: str | None):
    if not nit or not nombre_proveedor:
        return
    try:
        # Best-effort sync. If the schema does not yet include nombre_proveedor,
        # we silently skip to avoid interrupting invoice ingestion.
        supabase.table("config_cuentas").update({
            "nombre_proveedor": nombre_proveedor
        }).eq("nit_proveedor", nit).execute()
    except Exception as exc:
        print(f"No se pudo sincronizar nombre_proveedor en config_cuentas: {exc}")


def find_factura_by_cufe(cufe: str | None):
    if not cufe:
        return None
    res = supabase.table("facturas").select("*").eq("cufe", cufe).limit(1).execute()
    return res.data[0] if res.data else None


def get_successful_causacion(factura_id: str):
    res = (
        supabase.table("causaciones")
        .select("alegra_bill_id, estado, created_at")
        .eq("factura_id", factura_id)
        .eq("estado", "exitoso")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def mark_factura_estado(factura_id: str, estado: str):
    supabase.table("facturas").update({"estado": estado}).eq("id", factura_id).execute()

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
        factura_res = supabase.table("facturas").insert(factura_data).execute()
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
    
    supabase.table("items_factura").insert(items).execute()
    return {"factura_id": factura_id, "duplicado": False}

def log_email(email_log: dict):
    supabase.table("logs_email").upsert(email_log, on_conflict="mensaje_id").execute()

def save_causacion(causacion_data: dict):
    supabase.table("causaciones").insert(causacion_data).execute()
