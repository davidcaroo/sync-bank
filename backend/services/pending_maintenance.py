import asyncio
import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as date_parser

from repositories.config_repository import get_config_cuenta
from repositories.db_utils import run_in_executor
from services.factura_service import factura_service
from services.provider_mapping_service import provider_mapping_service
from services.xml_parser import DianEventError, parse_xml_dian

logger = logging.getLogger("pending_maintenance")

state = {
    "running": False,
    "total": 0,
    "revisadas": 0,
    "eventos_ignorados": 0,
    "ya_en_alegra": 0,
    "prefill": 0,
    "sin_regla": 0,
    "errores": 0,
}
_task: asyncio.Task | None = None
SCHEDULED_WINDOW_DAYS = 60


def _recent(rows: list, days: int = SCHEDULED_WINDOW_DAYS) -> list:
    """Rows emitted in the last `days`; rows without a date are kept."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept = []
    for row in rows:
        issued = row.get("fecha_emision")
        if isinstance(issued, str):
            issued = date_parser.parse(issued)
        if issued and issued.tzinfo is None:
            issued = issued.replace(tzinfo=timezone.utc)
        if not issued or issued >= cutoff:
            kept.append(row)
    return kept


async def _rule_for(
    nit: str, nombre: str | None, cache: dict, relearn: bool
) -> dict | None:
    if nit in cache:
        return cache[nit]
    config = await run_in_executor(lambda: get_config_cuenta(nit))
    computed = None
    if not config or (relearn and config.get("source") != "manual"):
        # Relearn from the learning window; manual rules are never touched.
        computed = await provider_mapping_service.compute_and_save_mapping(
            nit, nombre
        )
        config = await run_in_executor(lambda: get_config_cuenta(nit))
    rule = None
    if config and config.get("id_cuenta_alegra"):
        rule = {
            "cuenta": config["id_cuenta_alegra"],
            "centro": config.get("id_centro_costo_alegra"),
            "source": config.get("source") or "config",
            "confidence": float(config.get("confianza") or 1.0),
        }
    else:
        hint = await provider_mapping_service.suggest_mapping_from_history(
            nit, min_occurrences=1, min_share=0.6
        )
        if not hint and (computed or {}).get("source") == "sugerida":
            hint = computed
        if hint and hint.get("cuenta"):
            rule = {
                "cuenta": hint["cuenta"],
                "centro": hint.get("centro_costo"),
                "source": "sugerida" if hint.get("source") == "sugerida" else "historical",
                "confidence": float(hint.get("confidence") or 0.0),
            }
    cache[nit] = rule
    return rule


async def _process(factura_id: str, cache: dict, relearn: bool) -> None:
    repo = factura_service._factura_repository
    factura = await repo.get_factura_with_items(factura_id)
    if not factura or factura.get("estado") != "pendiente":
        return

    if factura.get("xml_raw"):
        try:
            parse_xml_dian(factura["xml_raw"])
        except DianEventError:
            await repo.update_factura_fields(factura_id, {"estado": "ignorado"})
            state["eventos_ignorados"] += 1
            return
        except Exception:
            pass

    if (await factura_service.marcar_si_ya_esta_en_alegra(factura_id)).get(
        "status"
    ) == "already_in_alegra":
        state["ya_en_alegra"] += 1
        return

    items = [i for i in factura.get("items_factura") or [] if not i.get("cuenta_contable_alegra")]
    if not items:
        return
    rule = await _rule_for(
        factura.get("nit_proveedor"), factura.get("nombre_proveedor"), cache, relearn
    )
    if not rule:
        state["sin_regla"] += 1
        return
    for item in items:
        await repo.update_item_fields(
            item["id"],
            {
                "cuenta_contable_alegra": rule["cuenta"],
                "centro_costo_alegra": rule["centro"],
                "prefill_source": rule["source"],
                "confidence": rule["confidence"],
            },
        )
    state["prefill"] += 1


async def _run(relearn: bool) -> None:
    cache: dict = {}
    try:
        res = await factura_service._factura_repository.get_facturas_paginated(
            page=1, page_size=500, estado="pendiente"
        )
        rows = res.data or []
        if not relearn:
            rows = _recent(rows)
        state["total"] = len(rows)
        for row in rows:
            try:
                await _process(str(row["id"]), cache, relearn)
            except Exception:
                state["errores"] += 1
                logger.exception("maintenance_failed", extra={"factura_id": row.get("id")})
            state["revisadas"] += 1
    finally:
        state["running"] = False


def _reset() -> None:
    for key in state:
        state[key] = False if key == "running" else 0
    state["running"] = True


def start() -> dict:
    global _task
    if not state["running"]:
        _reset()
        _task = asyncio.create_task(_run(relearn=True))
    return dict(state)


async def run_scheduled() -> None:
    """Periodic run: checks Alegra and prefills, without relearning existing rules."""
    if state["running"]:
        return
    _reset()
    await _run(relearn=False)
