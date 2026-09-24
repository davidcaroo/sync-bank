from dataclasses import dataclass
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from config import settings
from repositories.database import connection, transaction
from services.provider_mapping.normalization import normalize_nit


FACTURA_COLUMNS = (
    "cufe",
    "numero_factura",
    "fecha_emision",
    "fecha_vencimiento",
    "nit_proveedor",
    "nombre_proveedor",
    "nit_receptor",
    "subtotal",
    "iva",
    "rete_fuente",
    "rete_ica",
    "rete_iva",
    "total",
    "moneda",
    "xml_raw",
    "estado",
    "cargos_adicionales",
    "anticipos",
    "redondeo",
    "total_calculado",
    "diferencia_centavos",
    "validacion_total",
    "parsed_version",
    "calculo_exacto",
)
FACTURA_UPDATE_COLUMNS = frozenset(FACTURA_COLUMNS) - {"cufe"}
ITEM_UPDATE_COLUMNS = frozenset(
    {"cuenta_contable_alegra", "centro_costo_alegra", "prefill_source", "confidence"}
)


@dataclass(frozen=True)
class QueryResult:
    data: list[dict[str, Any]]
    count: int


def find_factura_by_cufe(cufe: str | None) -> dict[str, Any] | None:
    if not cufe:
        return None
    with connection() as conn:
        return conn.execute(
            "select * from facturas where cufe = %s limit 1", (cufe,)
        ).fetchone()


def get_successful_causacion(factura_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(
            """
            select alegra_bill_id, estado, created_at from causaciones
            where factura_id = %s and estado = 'exitoso'
            order by created_at desc limit 1
            """,
            (factura_id,),
        ).fetchone()


def mark_factura_estado(factura_id: str, estado: str) -> None:
    with transaction() as conn:
        conn.execute(
            "update facturas set estado = %s, updated_at = now() where id = %s",
            (estado, factura_id),
        )


def save_factura(
    factura_data: dict[str, Any], items: list[dict[str, Any]]
) -> dict[str, Any]:
    columns = [column for column in FACTURA_COLUMNS if column in factura_data]
    if not columns:
        raise ValueError("La factura no contiene campos permitidos")
    insert = sql.SQL(
        "insert into facturas ({}) values ({}) "
        "on conflict (cufe) where cufe is not null and btrim(cufe) <> '' "
        "do nothing returning id"
    ).format(
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    with transaction() as conn:
        row = conn.execute(
            insert, tuple(factura_data[column] for column in columns)
        ).fetchone()
        if row is None:
            existing = conn.execute(
                "select id from facturas where cufe = %s limit 1",
                (factura_data.get("cufe"),),
            ).fetchone()
            if existing is None:
                raise RuntimeError("No se pudo resolver la factura duplicada")
            return {"factura_id": existing["id"], "duplicado": True}

        factura_id = row["id"]
        if items:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into items_factura
                      (factura_id, descripcion, cantidad, precio_unitario, descuento,
                       iva_porcentaje, total_linea, cuenta_contable_alegra,
                       centro_costo_alegra, prefill_source, confidence)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            factura_id,
                            item.get("descripcion", ""),
                            item.get("cantidad", 0),
                            item.get("precio_unitario", 0),
                            item.get("descuento", 0),
                            item.get("iva_porcentaje", 19),
                            item.get("total_linea", 0),
                            item.get("cuenta_contable_alegra"),
                            item.get("centro_costo_alegra"),
                            item.get("prefill_source"),
                            item.get("confidence"),
                        )
                        for item in items
                    ],
                )
        return {"factura_id": factura_id, "duplicado": False}


def get_facturas_stats() -> list[dict[str, Any]]:
    with connection() as conn:
        return conn.execute(
            "select estado, created_at from facturas "
            "where fecha_emision is null or fecha_emision >= %s",
            (settings.MIN_ISSUE_DATE,),
        ).fetchall()


def get_facturas_paginated(
    *,
    page: int,
    page_size: int,
    estado: str | None = None,
    proveedor: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> QueryResult:
    clauses: list[str] = ["(f.fecha_emision is null or f.fecha_emision >= %s)"]
    params: list[Any] = [settings.MIN_ISSUE_DATE]
    for clause, value in (
        ("f.estado = %s", estado),
        ("f.nombre_proveedor ilike %s", f"%{proveedor}%" if proveedor else None),
        ("f.fecha_emision >= %s", desde),
        ("f.fecha_emision <= %s", hasta),
    ):
        if value is not None:
            clauses.append(clause)
            params.append(value)
    where = " where " + " and ".join(clauses) if clauses else ""
    offset = (page - 1) * page_size
    with connection() as conn:
        count = conn.execute(
            f"select count(*) as count from facturas f{where}", params
        ).fetchone()["count"]
        rows = conn.execute(
            f"""
            select f.*, coalesce(
                jsonb_agg(to_jsonb(i)) filter (where i.id is not null), '[]'::jsonb
            ) as items_factura
            from facturas f left join items_factura i on i.factura_id = f.id
            {where}
            group by f.id order by f.created_at desc limit %s offset %s
            """,
            (*params, page_size, offset),
        ).fetchall()
    return QueryResult(data=rows, count=count)


def get_factura_with_items(factura_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(
            """
            select f.*, coalesce(
                jsonb_agg(to_jsonb(i)) filter (where i.id is not null), '[]'::jsonb
            ) as items_factura
            from facturas f left join items_factura i on i.factura_id = f.id
            where f.id = %s group by f.id
            """,
            (factura_id,),
        ).fetchone()


def _update_factura_or_item(
    table: str, row_id: str, payload: dict[str, Any], allowed: frozenset[str]
) -> dict[str, Any] | None:
    unknown = set(payload) - allowed
    if not payload or unknown:
        raise ValueError(f"Campos no permitidos: {sorted(unknown)}")
    columns = list(payload)
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in columns
    )
    updated_at = sql.SQL(", updated_at = now()") if table == "facturas" else sql.SQL("")
    statement = sql.SQL("update {} set {}{} where id = %s returning *").format(
        sql.Identifier(table), assignments, updated_at
    )
    with transaction() as conn:
        return conn.execute(
            statement, (*[payload[column] for column in columns], row_id)
        ).fetchone()


def update_factura_fields(
    factura_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    return _update_factura_or_item(
        "facturas", factura_id, payload, FACTURA_UPDATE_COLUMNS
    )


def update_item_fields(item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _update_factura_or_item(
        "items_factura", item_id, payload, ITEM_UPDATE_COLUMNS
    )


def list_provider_nits() -> list[str]:
    with connection() as conn:
        rows = conn.execute(
            "select distinct btrim(nit_proveedor) as nit_proveedor from facturas "
            "where nit_proveedor is not null and btrim(nit_proveedor) <> '' order by 1"
        ).fetchall()
    return [row["nit_proveedor"] for row in rows]


def list_confirmed_provider_mappings(nit_proveedor: str) -> list[dict[str, Any]]:
    """One row per successfully caused invoice with its item account/cost-center pairs."""
    nit = normalize_nit(nit_proveedor)
    if not nit:
        return []
    with connection() as conn:
        return conn.execute(
            r"""
            select f.id,
                   jsonb_agg(
                       jsonb_build_object(
                           'cuenta', i.cuenta_contable_alegra,
                           'centro_costo', i.centro_costo_alegra
                       )
                   ) as mappings
            from facturas f
            join items_factura i on i.factura_id = f.id
            where regexp_replace(coalesce(f.nit_proveedor, ''), '\D', '', 'g') = %s
              and (f.fecha_emision is null or f.fecha_emision >= %s)
              and exists (
                  select 1 from causaciones c
                  where c.factura_id = f.id and c.estado = 'exitoso'
              )
            group by f.id
            order by f.created_at
            """,
            (nit, settings.LEARNING_START_DATE),
        ).fetchall()


def save_causacion(payload: dict[str, Any]) -> None:
    columns = (
        "factura_id",
        "alegra_bill_id",
        "alegra_response",
        "estado",
        "intentos",
        "error_msg",
    )
    values = [payload.get(column) for column in columns]
    values[2] = Jsonb(values[2]) if values[2] is not None else None
    with transaction() as conn:
        conn.execute(
            """
            insert into causaciones
              (factura_id, alegra_bill_id, alegra_response, estado, intentos, error_msg)
            values (%s, %s, %s, %s, %s, %s)
            """,
            values,
        )
