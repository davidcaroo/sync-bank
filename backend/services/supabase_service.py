import logging

from supabase import create_client, Client

from config import settings
from repositories.db_utils import execute_with_retry

logger = logging.getLogger("supabase")


def _resolve_supabase_server_key() -> str:
    if settings.SUPABASE_SERVICE_KEY:
        return settings.SUPABASE_SERVICE_KEY

    if settings.SUPABASE_REQUIRE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_KEY es requerido para el backend. "
            "Desactiva SUPABASE_REQUIRE_SERVICE_KEY solo para entornos de migracion controlada."
        )

    if settings.SUPABASE_KEY:
        logger.warning("using_legacy_supabase_key_fallback")
        return settings.SUPABASE_KEY

    raise RuntimeError("SUPABASE_SERVICE_KEY o SUPABASE_KEY es requerido")


supabase: Client = create_client(settings.SUPABASE_URL, _resolve_supabase_server_key())


def log_email(email_log: dict):
    execute_with_retry(lambda: supabase.table("logs_email").upsert(email_log, on_conflict="mensaje_id").execute())


def save_causacion(causacion_data: dict):
    execute_with_retry(lambda: supabase.table("causaciones").insert(causacion_data).execute())
