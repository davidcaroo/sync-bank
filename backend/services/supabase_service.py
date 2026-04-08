from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def get_config_cuenta(nit: str):
    res = supabase.table("config_cuentas").select("*").eq("nit_proveedor", nit).execute()
    return res.data[0] if res.data else None

def save_factura(factura_data: dict, items: list):
    # Insert factura
    factura_res = supabase.table("facturas").insert(factura_data).execute()
    if not factura_res.data:
        return None
    
    factura_id = factura_res.data[0]["id"]
    
    # Insert items
    for item in items:
        item["factura_id"] = factura_id
    
    supabase.table("items_factura").insert(items).execute()
    return factura_id

def log_email(email_log: dict):
    supabase.table("logs_email").upsert(email_log, on_conflict="mensaje_id").execute()

def save_causacion(causacion_data: dict):
    supabase.table("causaciones").insert(causacion_data).execute()
