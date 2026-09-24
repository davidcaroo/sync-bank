import logging
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException

from config import settings
from repositories.config_repository import get_config_cuenta, sync_config_proveedor_nombre
from repositories.db_utils import run_in_executor
from repositories.factura_async_repository import (
    SyncCausacionRepositoryAdapter,
    SyncFacturaRepositoryAdapter,
)
from repositories.ingestion_adapters import SyncProviderConfigRepositoryAdapter
from services.factura_service import factura_service
from services.provider_mapping.normalization import nit_key, normalize_nit

CENT = Decimal("0.01")
BLOCKED_ESTADO = "autocausacion_bloqueada"
# Provider not opted in: nothing to report. Anything else is an opted-in rule
# that was blocked by a guard and deserves a visible reason.
NOT_OPTED_IN = {"inactive_rule", "not_authorized"}
# Alegra already has the bill; causar_factura marked the invoice procesado.
ALREADY_IN_ALEGRA = {"DUPLICADO_ALEGRA", "FACTURA_YA_CAUSADA"}


@dataclass(frozen=True)
class AutoCausacionDecision:
    eligible: bool
    reason: str


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def _same_id(left, right) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def evaluate_auto_causacion(
    factura: dict, config: dict | None
) -> AutoCausacionDecision:
    """Pure guard: eligible only for an opted-in manual rule and a coherent XML invoice."""
    if not config or not config.get("activo"):
        return AutoCausacionDecision(False, "inactive_rule")
    if config.get("source") != "manual" or not config.get("auto_causar"):
        return AutoCausacionDecision(False, "not_authorized")
    if not config.get("id_cuenta_alegra"):
        return AutoCausacionDecision(False, "missing_account")
    if not config.get("id_centro_costo_alegra"):
        return AutoCausacionDecision(False, "missing_cost_center")
    if normalize_nit(factura.get("nit_proveedor")) != normalize_nit(
        config.get("nit_proveedor")
    ):
        return AutoCausacionDecision(False, "nit_mismatch")
    company = nit_key(settings.COMPANY_NIT)
    if not company or nit_key(factura.get("nit_receptor")) != company:
        return AutoCausacionDecision(False, "receiver_nit_mismatch")
    if not factura.get("xml_raw"):
        return AutoCausacionDecision(False, "not_xml")
    if factura.get("estado") != "pendiente":
        return AutoCausacionDecision(False, "not_pending")
    if factura.get("cufe") in {None, "", "SIN-CUFE"}:
        return AutoCausacionDecision(False, "missing_cufe")
    if factura.get("numero_factura") in {None, "", "SIN-NUMERO"}:
        return AutoCausacionDecision(False, "missing_number")
    if str(factura.get("moneda") or "").upper() != "COP":
        return AutoCausacionDecision(False, "unsupported_currency")

    items = factura.get("items_factura") or []
    if not items:
        return AutoCausacionDecision(False, "missing_items")
    if _money(factura.get("total")) <= 0:
        return AutoCausacionDecision(False, "invalid_total")
    if any(
        not _same_id(item.get("cuenta_contable_alegra"), config["id_cuenta_alegra"])
        or not _same_id(
            item.get("centro_costo_alegra"), config["id_centro_costo_alegra"]
        )
        for item in items
    ):
        return AutoCausacionDecision(False, "item_mapping_mismatch")

    lines_total = sum((_money(item.get("total_linea")) for item in items), Decimal(0))
    if abs(lines_total - _money(factura.get("subtotal"))) > CENT:
        return AutoCausacionDecision(False, "line_total_mismatch")

    expected_total = (
        _money(factura.get("subtotal"))
        + _money(factura.get("iva"))
        - _money(factura.get("rete_fuente"))
        - _money(factura.get("rete_ica"))
        - _money(factura.get("rete_iva"))
    )
    if abs(expected_total - _money(factura.get("total"))) > CENT:
        return AutoCausacionDecision(False, "invoice_total_mismatch")
    return AutoCausacionDecision(True, "authorized")


class AutoCausacionService:
    def __init__(
        self,
        *,
        factura_repository=None,
        config_repository=None,
        causacion_repository=None,
        factura_service_=None,
        logger=None,
    ) -> None:
        self._factura_repository = factura_repository or SyncFacturaRepositoryAdapter(
            run_in_executor=run_in_executor
        )
        self._config_repository = (
            config_repository
            or SyncProviderConfigRepositoryAdapter(
                run_in_executor=run_in_executor,
                get_config_cuenta=get_config_cuenta,
                sync_config_proveedor_nombre=sync_config_proveedor_nombre,
            )
        )
        self._causacion_repository = (
            causacion_repository
            or SyncCausacionRepositoryAdapter(run_in_executor=run_in_executor)
        )
        self._factura_service = factura_service_ or factura_service
        self._logger = logger or logging.getLogger("auto_causacion")

    async def _record_block(self, factura_id: str, reason: str) -> None:
        try:
            await self._causacion_repository.save_causacion(
                {
                    "factura_id": factura_id,
                    "alegra_bill_id": None,
                    "alegra_response": {"code": reason},
                    "estado": BLOCKED_ESTADO,
                    "intentos": 0,
                    "error_msg": reason,
                }
            )
        except Exception:
            self._logger.exception(
                "auto_causacion_block_not_recorded", extra={"factura_id": factura_id}
            )

    async def try_cause_from_imap_xml(self, factura_id: str) -> dict:
        """Called only for an XML invoice that was just created from IMAP."""
        factura = await self._factura_repository.get_factura_with_items(factura_id)
        if not factura:
            return {"status": "skipped", "reason": "not_found"}

        config = await self._config_repository.get_config_cuenta(
            factura.get("nit_proveedor")
        )
        decision = evaluate_auto_causacion(factura, config)
        if not decision.eligible:
            if decision.reason in NOT_OPTED_IN:
                return {"status": "skipped", "reason": decision.reason}
            self._logger.warning(
                "auto_causacion_blocked",
                extra={"factura_id": factura_id, "reason": decision.reason},
            )
            await self._record_block(factura_id, decision.reason)
            return {"status": "pending", "reason": decision.reason}

        if await self._factura_repository.get_successful_causacion(factura_id):
            return {"status": "skipped", "reason": "already_caused"}

        try:
            response = await self._factura_service.causar_factura(factura_id)
            return {"status": "caused", "alegra": response}
        except HTTPException as exc:
            code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
            if code in ALREADY_IN_ALEGRA:
                # The bill exists in Alegra; keep the invoice as procesado.
                return {"status": "skipped", "reason": code.lower()}
            reason = code or "alegra_error"
        except Exception:
            reason = "alegra_error"
            self._logger.exception(
                "auto_causacion_failed", extra={"factura_id": factura_id}
            )

        await self._factura_repository.update_factura_fields(
            factura_id, {"estado": "pendiente"}
        )
        await self._record_block(factura_id, reason)
        return {"status": "pending", "reason": reason}


auto_causacion_service = AutoCausacionService()
