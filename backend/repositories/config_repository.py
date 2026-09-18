import logging
from typing import Any

from psycopg import sql

from repositories.database import connection, transaction
from services.provider_mapping.normalization import normalize_nit


logger = logging.getLogger(__name__)
CONFIG_COLUMNS = frozenset(
    {
        "nit_proveedor",
        "nombre_proveedor",
        "id_cuenta_alegra",
        "id_centro_costo_alegra",
        "confianza",
        "activo",
        "source",
        "auto_causar",
    }
)


_NIT_DIGITS = r"regexp_replace(nit_proveedor, '\D', '', 'g')"


def get_config_cuenta(nit: str) -> dict[str, Any] | None:
    digits = normalize_nit(nit)
    if not digits:
        return None
    with connection() as conn:
        return conn.execute(
            f"select * from config_cuentas where {_NIT_DIGITS} = %s "
            "and activo = true limit 1",
            (digits,),
        ).fetchone()


def sync_config_proveedor_nombre(nit: str | None, nombre_proveedor: str | None) -> None:
    digits = normalize_nit(nit)
    if not digits or not nombre_proveedor:
        return
    try:
        with transaction() as conn:
            conn.execute(
                "update config_cuentas set nombre_proveedor = %s, updated_at = now() "
                f"where {_NIT_DIGITS} = %s",
                (nombre_proveedor, digits),
            )
    except Exception:
        logger.exception("config_provider_name_sync_failed", extra={"nit": nit})


def list_config_cuentas(activo: bool | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        if activo is None:
            return conn.execute(
                "select * from config_cuentas order by created_at desc"
            ).fetchall()
        return conn.execute(
            "select * from config_cuentas where activo = %s order by created_at desc",
            (activo,),
        ).fetchall()


def _validated_payload(
    payload: dict[str, Any], *, require_identity: bool = False
) -> dict[str, Any]:
    unknown = set(payload) - CONFIG_COLUMNS
    if not payload or unknown:
        raise ValueError(f"Campos no permitidos: {sorted(unknown)}")
    if require_identity and (
        not payload.get("nit_proveedor") or not payload.get("id_cuenta_alegra")
    ):
        raise ValueError("nit_proveedor e id_cuenta_alegra son requeridos")
    return payload


def _with_normalized_nit(payload: dict[str, Any]) -> dict[str, Any]:
    if "nit_proveedor" in payload:
        return {**payload, "nit_proveedor": normalize_nit(payload["nit_proveedor"])}
    return payload


def create_config_cuenta(payload: dict[str, Any]) -> dict[str, Any] | None:
    payload = _validated_payload(
        _with_normalized_nit(payload), require_identity=True
    )
    columns = list(payload)
    statement = sql.SQL(
        "insert into config_cuentas ({}) values ({}) returning *"
    ).format(
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with transaction() as conn:
        return conn.execute(
            statement, tuple(payload[column] for column in columns)
        ).fetchone()


def update_config_cuenta(
    config_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    payload = _validated_payload(_with_normalized_nit(payload))
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


def _same_rule(current: dict[str, Any], incoming: dict[str, Any]) -> bool:
    def number(value):
        return None if value is None else round(float(value), 6)

    return all(
        (
            current["nombre_proveedor"] == incoming["nombre_proveedor"],
            current["id_cuenta_alegra"] == incoming["id_cuenta_alegra"],
            current["id_centro_costo_alegra"] == incoming["id_centro_costo_alegra"],
            number(current["confianza"]) == number(incoming["confianza"]),
            current["activo"] == incoming["activo"],
            current["source"] == incoming["source"],
            current["auto_causar"] == incoming["auto_causar"],
        )
    )


def save_config_cuenta(
    nit_proveedor: str,
    nombre_proveedor: str | None,
    id_cuenta_alegra: str,
    id_centro_costo_alegra: str | None = None,
    confianza: float | None = None,
    activo: bool = True,
    source: str = "auto",
    auto_causar: bool = False,
) -> dict[str, Any] | None:
    """Upsert a provider rule. A manual rule is never replaced by a non-manual
    save, and the audit trail only records real changes."""
    nit = normalize_nit(nit_proveedor)
    if not nit or not id_cuenta_alegra:
        return None
    incoming = {
        "nombre_proveedor": nombre_proveedor,
        "id_cuenta_alegra": id_cuenta_alegra,
        "id_centro_costo_alegra": id_centro_costo_alegra,
        "confianza": confianza,
        "activo": activo,
        "source": source,
        "auto_causar": auto_causar,
    }
    with transaction() as conn:
        current = conn.execute(
            f"select * from config_cuentas where {_NIT_DIGITS} = %s for update",
            (nit,),
        ).fetchone()
        if current and current.get("source") == "manual" and source != "manual":
            return current
        if current and _same_rule(current, incoming):
            return current

        values = (
            incoming["nombre_proveedor"],
            incoming["id_cuenta_alegra"],
            incoming["id_centro_costo_alegra"],
            incoming["confianza"],
            incoming["activo"],
            incoming["source"],
            incoming["auto_causar"],
        )
        if current is None:
            row = conn.execute(
                """
                insert into config_cuentas
                  (nit_proveedor, nombre_proveedor, id_cuenta_alegra,
                   id_centro_costo_alegra, confianza, activo, source, auto_causar)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (nit, *values),
            ).fetchone()
        else:
            row = conn.execute(
                """
                update config_cuentas set
                  nombre_proveedor = %s, id_cuenta_alegra = %s,
                  id_centro_costo_alegra = %s, confianza = %s, activo = %s,
                  source = %s, auto_causar = %s, updated_at = now()
                where id = %s
                returning *
                """,
                (*values, current["id"]),
            ).fetchone()
        conn.execute(
            """
            insert into config_cuentas_audit
              (nit_proveedor, id_cuenta_alegra, id_centro_costo_alegra, confianza,
               source, auto_causar)
            values (%s, %s, %s, %s, %s, %s)
            """,
            (
                nit,
                id_cuenta_alegra,
                id_centro_costo_alegra,
                confianza,
                source,
                auto_causar,
            ),
        )
    return row
