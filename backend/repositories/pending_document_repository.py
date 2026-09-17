import json
from typing import Any

from repositories.database import connection, transaction


def save_pending_document(payload: dict[str, Any]) -> None:
    with transaction() as conn:
        conn.execute(
            """
            insert into documentos_pendientes
              (message_id, attachment_sha256, file_name, page_start, page_end,
               raw_text, candidate, missing_fields, warnings)
            values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            on conflict (attachment_sha256, page_start, page_end) do nothing
            """,
            (
                payload["message_id"],
                payload["attachment_sha256"],
                payload["file_name"],
                payload["page_start"],
                payload["page_end"],
                payload["raw_text"],
                json.dumps(payload["candidate"]),
                json.dumps(payload.get("missing_fields", [])),
                json.dumps(payload.get("warnings", [])),
            ),
        )


def list_pending_documents() -> list[dict[str, Any]]:
    with connection() as conn:
        return conn.execute(
            "select * from documentos_pendientes where estado = 'requiere_revision' order by created_at desc"
        ).fetchall()


def resolve_pending_document(document_id: str, factura_id: str | None) -> None:
    with transaction() as conn:
        conn.execute(
            """
            update documentos_pendientes set estado = 'confirmado', factura_id = %s,
              resolved_at = now() where id = %s and estado = 'requiere_revision'
            """,
            (factura_id, document_id),
        )
