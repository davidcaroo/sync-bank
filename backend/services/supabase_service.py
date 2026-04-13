from supabase import create_client, Client
from config import settings
from repositories.db_utils import execute_with_retry

service_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
if not service_key:
    raise RuntimeError("SUPABASE_SERVICE_KEY o SUPABASE_KEY es requerido")
supabase: Client = create_client(settings.SUPABASE_URL, service_key)


def log_email(email_log: dict):
    execute_with_retry(lambda: supabase.table("logs_email").upsert(email_log, on_conflict="mensaje_id").execute())


def save_causacion(causacion_data: dict):
    execute_with_retry(lambda: supabase.table("causaciones").insert(causacion_data).execute())
