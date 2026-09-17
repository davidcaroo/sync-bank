import logging
from typing import Any

from psycopg import sql

from repositories.database import connection, transaction


logger = logging.getLogger(__name__)
CONFIG_COLUMNS = frozenset(
    {
        "nit_proveedor", "nombre_proveedor", "id_cuenta_alegra",
        "id_centro_costo_alegra", "confianza", "activo", "source",
    }
)


def get_config_cuenta(nit: str) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(
            "select * from config_cuentas where nit_proveedor = %s and activo = true limit 1",
            (nit,),
        ).fetchone()


def sync_config_proveedor_nombre(nit: str | None, nombre_proveedor: str | None) -> None:
    if not nit or not nombre_proveedor:
        return
    try:
        with transaction() as conn:
            conn.execute(
                "update config_cuentas set nombre_proveedor = %s, updated_at = now() where nit_proveedor = %s",
                (nombre_proveedor, nit),
            )
    except Exception:
        logger.exception("config_provider_name_sync_failed", extra={"nit": nit})


def list_config_cuentas(activo: bool | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        if activo is None:
            return conn.execute("select * from config_cuentas order by created_at desc").fetchall()
        return conn.execute(
            "select * from config_cuentas where activo = %s order by created_at desc",
            (activo,),
        ).fetchall()


def _validated_payload(payload: dict[str, Any], *, require_identity: bool = False) -> dict[str, Any]:
    unknown = set(payload) - CONFIG_COLUMNS
    if not payload or unknown:
        raise ValueError(f"Campos no permitidos: {sorted(unknown)}")
    if require_identity and (not payload.get("nit_proveedor") or not payload.get("id_cuenta_alegra")):
        raise ValueError("nit_proveedor e id_cuenta_alegra son requeridos")
    return payload


def create_config_cuenta(payload: dict[str, Any]) -> dict[str, Any] | None:
    payload = _validated_payload(payload, require_identity=True)
    columns = list(payload)
    statement = sql.SQL("insert into config_cuentas ({}) values ({}) returning *").format(
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with transaction() as conn:
        return conn.execute(statement, tuple(payload[column] for column in columns)).fetchone()


def update_config_cuenta(config_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    payload = _validated_payload(payload)
    columns = list(payload)
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in columns
    )
    statement = sql.SQL(
        "update config_cuentas set {}, updated_at = now() where id = %s returning *"
    ).format(assignments)
    with transaction() as conn:
        return conn.execute(
            statement, (*[payload[column] for column in columns], config_id)
        ).fetchone()


def delete_config_cuenta(config_id: str) -> dict[str, Any] | None:
    with transaction() as conn:
        return conn.execute(
            "delete from config_cuentas where id = %s returning *", (config_id,)
        ).fetchone()


def save_config_cuenta(
    nit_proveedor: str,
    nombre_proveedor: str | None,
    id_cuenta_alegra: str,
    id_centro_costo_alegra: str | None = None,
    confianza: float | None = None,
    activo: bool = True,
    source: str = "auto",
) -> dict[str, Any] | None:
    if not nit_proveedor or not id_cuenta_alegra:
        return None
    with transaction() as conn:
        row = conn.execute(
            """
            insert into config_cuentas
              (nit_proveedor, nombre_proveedor, id_cuenta_alegra,
               id_centro_costo_alegra, confianza, activo, source)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (nit_proveedor) do update set
              nombre_proveedor = excluded.nombre_proveedor,
              id_cuenta_alegra = excluded.id_cuenta_alegra,
              id_centro_costo_alegra = excluded.id_centro_costo_alegra,
              confianza = excluded.confianza,
              activo = excluded.activo,
              source = excluded.source,
              updated_at = now()
            returning *
            """,
            (
                nit_proveedor, nombre_proveedor, id_cuenta_alegra,
                id_centro_costo_alegra, confianza, activo, source,
            ),
        ).fetchone()
        conn.execute(
            """
            insert into config_cuentas_audit
              (nit_proveedor, id_cuenta_alegra, id_centro_costo_alegra, confianza, source)
            values (%s, %s, %s, %s, %s)
            """,
            (nit_proveedor, id_cuenta_alegra, id_centro_costo_alegra, confianza, source),
        )
    return row
