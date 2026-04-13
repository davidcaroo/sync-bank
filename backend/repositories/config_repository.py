from services.supabase_service import supabase
from repositories.db_utils import execute_with_retry


def get_config_cuenta(nit: str):
    res = execute_with_retry(
        lambda: supabase.table("config_cuentas")
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
        execute_with_retry(lambda: supabase.table("config_cuentas").update({
            "nombre_proveedor": nombre_proveedor
        }).eq("nit_proveedor", nit).execute())
    except Exception as exc:
        print(f"No se pudo sincronizar nombre_proveedor en config_cuentas: {exc}")


def list_config_cuentas(activo: bool | None = None):
    query = supabase.table("config_cuentas").select("*")
    if activo is not None:
        query = query.eq("activo", activo)
    res = execute_with_retry(lambda: query.order("created_at", desc=True).execute())
    return res.data or []


def create_config_cuenta(payload: dict):
    res = execute_with_retry(lambda: supabase.table("config_cuentas").insert(payload).execute())
    return res.data[0] if res.data else None


def update_config_cuenta(config_id: str, payload: dict):
    res = execute_with_retry(lambda: supabase.table("config_cuentas").update(payload).eq("id", config_id).execute())
    return res.data[0] if res.data else None


def delete_config_cuenta(config_id: str):
    res = execute_with_retry(lambda: supabase.table("config_cuentas").delete().eq("id", config_id).execute())
    return res.data[0] if res.data else None


def save_config_cuenta(
    nit_proveedor: str,
    nombre_proveedor: str | None,
    id_cuenta_alegra: str,
    id_centro_costo_alegra: str | None = None,
    confianza: float | None = None,
    activo: bool = True,
    source: str = "auto",
):
    if not nit_proveedor or not id_cuenta_alegra:
        return None
    payload = {
        "nit_proveedor": nit_proveedor,
        "nombre_proveedor": nombre_proveedor,
        "id_cuenta_alegra": id_cuenta_alegra,
        "id_centro_costo_alegra": id_centro_costo_alegra,
        "confianza": confianza,
        "activo": activo,
        "source": source,
    }
    try:
        execute_with_retry(lambda: supabase.table("config_cuentas").upsert(payload, on_conflict="nit_proveedor").execute())
        try:
            audit_payload = {
                "nit_proveedor": nit_proveedor,
                "id_cuenta_alegra": id_cuenta_alegra,
                "id_centro_costo_alegra": id_centro_costo_alegra,
                "confianza": confianza,
                "source": source,
            }
            execute_with_retry(lambda: supabase.table("config_cuentas_audit").insert(audit_payload).execute())
        except Exception as aexc:
            print(f"No se pudo insertar audit config_cuentas_audit: {aexc}")
        return payload
    except Exception as exc:
        print(f"Error guardando config_cuentas para {nit_proveedor}: {exc}")
        return None
