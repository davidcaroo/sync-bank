from typing import Any

from repositories.database import connection, transaction


def upsert_email_log(payload: dict[str, Any]) -> None:
    if not payload.get("mensaje_id") or not payload.get("estado"):
        raise ValueError("mensaje_id y estado son requeridos")
    with transaction() as conn:
        conn.execute(
            """
            insert into logs_email
              (mensaje_id, remitente, asunto, estado, attachments_encontrados)
            values (%s, %s, %s, %s, %s)
            on conflict (mensaje_id) do update set
              remitente = excluded.remitente,
              asunto = excluded.asunto,
              estado = excluded.estado,
              attachments_encontrados = excluded.attachments_encontrados,
              updated_at = now()
            """,
            (
                payload["mensaje_id"], payload.get("remitente"), payload.get("asunto"),
                payload["estado"], payload.get("attachments_encontrados", 0),
            ),
        )


def list_logs_paginated(
    *, page: int, page_size: int, estado: str | None = None
) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * page_size
    where = " where estado = %s" if estado else ""
    params = (estado,) if estado else ()
    with connection() as conn:
        count = conn.execute(
            f"select count(*) as count from logs_email{where}", params
        ).fetchone()["count"]
        rows = conn.execute(
            f"select * from logs_email{where} order by created_at desc limit %s offset %s",
            (*params, page_size, offset),
        ).fetchall()
    return rows, count
