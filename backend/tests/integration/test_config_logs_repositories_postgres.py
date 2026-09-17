from repositories.config_repository import get_config_cuenta, save_config_cuenta
from repositories.database import connection
from repositories.logs_repository import list_logs_paginated, upsert_email_log


def test_save_config_writes_current_value_and_audit():
    save_config_cuenta("9001", "Proveedor", "5105", confianza=0.8, source="manual")

    row = get_config_cuenta("9001")
    with connection() as conn:
        audit_count = conn.execute(
            "select count(*) as count from config_cuentas_audit where nit_proveedor = %s",
            ("9001",),
        ).fetchone()["count"]

    assert row["id_cuenta_alegra"] == "5105"
    assert row["nombre_proveedor"] == "Proveedor"
    assert audit_count == 1


def test_email_log_upsert_is_idempotent():
    payload = {
        "mensaje_id": "msg-1",
        "remitente": "a@example.com",
        "asunto": "Factura",
        "estado": "procesado",
        "attachments_encontrados": 1,
    }
    upsert_email_log(payload)
    upsert_email_log({**payload, "estado": "error"})

    rows, count = list_logs_paginated(page=1, page_size=10)

    assert count == 1
    assert rows[0]["estado"] == "error"
