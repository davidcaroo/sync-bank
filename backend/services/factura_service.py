from datetime import datetime
import logging
import asyncio

import httpx
from dateutil import parser as date_parser
from fastapi import HTTPException

from models.factura import FacturaDIAN, FacturaItem
from repositories.db_utils import run_in_executor
from repositories.factura_repository import (
    get_successful_causacion,
    get_facturas_stats as repo_get_facturas_stats,
    get_facturas_paginated,
    get_factura_with_items,
    update_factura_fields,
    update_item_fields,
)
from services.alegra_service import alegra_service, AlegraDuplicateBillError
from services.ingestion_service import ingestion_service
from services.provider_mapping_service import provider_mapping_service
from services.supabase_service import save_causacion
from services.timezone_service import now_bogota, to_bogota
from services.xml_parser import parse_xml_dian

logger = logging.getLogger("facturas")


class FacturaService:
    async def _check_remote_bill_status(self, factura_data: dict, *, known_bill_id: str | None = None) -> dict:
        """Verify if the bill still exists in Alegra for this local invoice."""
        if known_bill_id:
            try:
                async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    bill = await alegra_service.get_bill_by_id(client, str(known_bill_id))
            except Exception:
                return {"verified": False, "exists": None, "bill_id": None}

            if bill:
                bill_id = bill.get("id") if isinstance(bill, dict) else known_bill_id
                return {
                    "verified": True,
                    "exists": True,
                    "bill_id": str(bill_id) if bill_id is not None else str(known_bill_id),
                }

            return {"verified": True, "exists": False, "bill_id": None}

        try:
            remote = await alegra_service.get_bill_accounting_by_invoice(
                nit_proveedor=factura_data.get("nit_proveedor"),
                numero_factura=factura_data.get("numero_factura"),
                max_pages=4,
            )
        except Exception:
            return {"verified": False, "exists": None, "bill_id": None}

        if remote and remote.get("bill_id"):
            return {
                "verified": True,
                "exists": True,
                "bill_id": remote.get("bill_id"),
            }

        return {"verified": True, "exists": False, "bill_id": None}

    async def _hydrate_items_from_alegra_if_needed(self, factura: dict) -> dict:
        if not factura:
            return factura

        estado = (factura.get("estado") or "").strip().lower()
        if estado not in {"duplicado", "procesado"}:
            return factura

        items = factura.get("items_factura") or []
        if not items:
            return factura

        has_missing_mapping = any(
            not (item.get("cuenta_contable_alegra") or item.get("centro_costo_alegra"))
            for item in items
        )
        if not has_missing_mapping:
            return factura

        try:
            remote = await alegra_service.get_bill_accounting_by_invoice(
                nit_proveedor=factura.get("nit_proveedor"),
                numero_factura=factura.get("numero_factura"),
            )
        except Exception:
            return factura

        if not remote:
            return factura

        remote_items = remote.get("items") or []
        if not remote_items:
            return factura

        updated = False
        for idx, item in enumerate(items):
            remote_item = None
            if idx < len(remote_items):
                remote_item = remote_items[idx]
            elif len(remote_items) == 1:
                remote_item = remote_items[0]

            if not remote_item:
                continue

            current_cuenta = item.get("cuenta_contable_alegra")
            current_centro = item.get("centro_costo_alegra")
            new_cuenta = remote_item.get("cuenta_contable_alegra")
            new_centro = remote_item.get("centro_costo_alegra")

            patch = {}
            if not current_cuenta and new_cuenta:
                patch["cuenta_contable_alegra"] = new_cuenta
            if not current_centro and new_centro:
                patch["centro_costo_alegra"] = new_centro

            if patch:
                try:
                    await run_in_executor(lambda: update_item_fields(item.get("id"), patch))
                except Exception:
                    continue

                item.update(patch)
                updated = True

        if updated:
            factura["items_factura"] = items

        if remote.get("bill_id"):
            factura["alegra_bill_id"] = remote.get("bill_id")

        return factura

    def _enrich_factura_monetary_fields(self, factura: dict) -> dict:
        if not factura:
            return factura

        subtotal = float(factura.get("subtotal") or 0)
        iva = float(factura.get("iva") or 0)
        rete_fuente = float(factura.get("rete_fuente") or 0)
        rete_ica = float(factura.get("rete_ica") or 0)
        rete_iva = float(factura.get("rete_iva") or 0)
        total_stored = float(factura.get("total") or 0)

        xml_raw = factura.get("xml_raw")
        if xml_raw:
            try:
                parsed = parse_xml_dian(xml_raw)
                subtotal = float(parsed.subtotal or 0)
                iva = float(parsed.iva or 0)
                rete_fuente = float(parsed.rete_fuente or 0)
                rete_ica = float(parsed.rete_ica or 0)
                rete_iva = float(parsed.rete_iva or 0)
                total_stored = float(parsed.total or total_stored)
            except Exception:
                pass

        factura["subtotal"] = subtotal
        factura["iva"] = iva
        factura["rete_fuente"] = rete_fuente
        factura["rete_ica"] = rete_ica
        factura["rete_iva"] = rete_iva
        factura["total_bruto"] = subtotal + iva
        factura["total_retenciones"] = rete_fuente + rete_ica + rete_iva
        factura["total_neto"] = total_stored
        factura["total"] = total_stored

        return factura

    def _normalize_items_prefill(self, items: list[dict]) -> list[dict]:
        for item in items:
            if "prefill_source" not in item or item.get("prefill_source") is None:
                item["prefill_source"] = "unknown"
            if "confidence" not in item:
                item["confidence"] = None
        return items

    def _preview_summary(self, results: list[dict], *, total_files: int, total_xml: int) -> dict:
        return {
            "total_files": total_files,
            "total_xml": total_xml,
            "valid": len([item for item in results if item.get("status") == "valid"]),
            "invalid": len([item for item in results if item.get("status") == "invalid"]),
            "duplicates": len([item for item in results if item.get("status") == "duplicate"]),
        }

    def _upload_summary(self, results: list[dict], *, total_files: int, total_xml: int) -> dict:
        return {
            "total_files": total_files,
            "total_xml": total_xml,
            "created": len([item for item in results if item.get("status") == "created"]),
            "duplicates": len([item for item in results if item.get("status") == "duplicate"]),
            "errors": len([item for item in results if item.get("status") in {"error", "invalid"}]),
        }

    async def preview_upload_facturas(self, files, *, apply_ai: bool = True, auto_apply_ai: bool = False):
        extracted = await ingestion_service.extract_xml_documents_from_upload(files)
        documents = extracted.get("documents") or []
        errors = extracted.get("errors") or []

        prefill_context = await ingestion_service.build_prefill_context(apply_ai=apply_ai)

        results = list(errors)
        sem = asyncio.Semaphore(3)

        async def _process_preview_doc(xml_doc):
            async with sem:
                return await ingestion_service.process_xml_document(
                    xml_doc,
                    persist=False,
                    apply_ai=apply_ai,
                    categories=prefill_context.get("categories"),
                    cost_centers=prefill_context.get("cost_centers"),
                    auto_apply_ai=auto_apply_ai,
                    preview_mode=True,
                )

        if documents:
            preview_results = await asyncio.gather(*[_process_preview_doc(doc) for doc in documents])
            results.extend(preview_results)

        return {
            "summary": self._preview_summary(
                results,
                total_files=len(files),
                total_xml=len(documents),
            ),
            "files": results,
        }

    async def upload_facturas(self, files, *, apply_ai: bool = True, auto_apply_ai: bool = False):
        extracted = await ingestion_service.extract_xml_documents_from_upload(files)
        documents = extracted.get("documents") or []
        errors = extracted.get("errors") or []

        prefill_context = await ingestion_service.build_prefill_context(apply_ai=apply_ai)

        results = list(errors)
        for xml_doc in documents:
            result = await ingestion_service.process_xml_document(
                xml_doc,
                persist=True,
                apply_ai=apply_ai,
                categories=prefill_context.get("categories"),
                cost_centers=prefill_context.get("cost_centers"),
                auto_apply_ai=auto_apply_ai,
                preview_mode=False,
            )
            results.append(result)

        return {
            "summary": self._upload_summary(
                results,
                total_files=len(files),
                total_xml=len(documents),
            ),
            "files": results,
        }

    async def get_facturas_stats(self):
        facturas = await run_in_executor(lambda: repo_get_facturas_stats())
        hoy = 0
        causadas = 0
        pendientes = 0
        errores = 0
        today_local = now_bogota().date()

        for factura in facturas:
            created_at = factura.get("created_at")
            if created_at:
                try:
                    created_dt = date_parser.parse(created_at)
                    created_local = to_bogota(created_dt)
                    created_local_date = created_local.date() if created_local else None
                    if created_local_date == today_local:
                        hoy += 1
                except Exception:
                    pass

            estado = factura.get("estado")
            if estado == "procesado":
                causadas += 1
            elif estado == "pendiente":
                pendientes += 1
            elif estado == "error":
                errores += 1

        return {"hoy": hoy, "causadas": causadas, "pendientes": pendientes, "errores": errores}

    async def get_facturas(
        self,
        *,
        page: int,
        page_size: int,
        estado: str | None = None,
        proveedor: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ):
        res = await run_in_executor(
            lambda: get_facturas_paginated(
                page=page,
                page_size=page_size,
                estado=estado,
                proveedor=proveedor,
                desde=desde,
                hasta=hasta,
            )
        )
        rows = res.data or []
        for row in rows:
            items = row.get("items_factura") or []
            row["items_factura"] = self._normalize_items_prefill(items)
        rows = [self._enrich_factura_monetary_fields(row) for row in rows]
        return {
            "data": rows,
            "count": res.count or 0,
            "page": page,
            "page_size": page_size,
        }

    async def get_factura(self, factura_id: str):
        factura = await run_in_executor(lambda: get_factura_with_items(factura_id))
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        factura = await self._hydrate_items_from_alegra_if_needed(factura)
        items = factura.get("items_factura") or []
        factura["items_factura"] = self._normalize_items_prefill(items)
        return self._enrich_factura_monetary_fields(factura)

    async def causar_factura(self, factura_id: str, overrides_map: dict | None = None):
        factura_data = await run_in_executor(lambda: get_factura_with_items(factura_id))
        if not factura_data:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        existing_success = await run_in_executor(lambda: get_successful_causacion(factura_id))
        known_bill_id = (
            str(existing_success.get("alegra_bill_id"))
            if existing_success and existing_success.get("alegra_bill_id") is not None
            else None
        )

        if factura_data.get("estado") == "procesado":
            remote_status = await self._check_remote_bill_status(factura_data, known_bill_id=known_bill_id)
            if remote_status.get("exists") is False:
                await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "pendiente"}))
                factura_data["estado"] = "pendiente"
            elif remote_status.get("exists") is None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "No se pudo verificar en Alegra si la factura sigue causada. Intenta nuevamente.",
                        "code": "NO_VERIFICADO_ALEGRA",
                    },
                )

        if factura_data.get("estado") == "procesado":
            detail = {
                "message": "Factura ya causada",
                "code": "FACTURA_YA_CAUSADA",
                "alegra_bill_id": remote_status.get("bill_id") if remote_status.get("bill_id") else (existing_success.get("alegra_bill_id") if existing_success else None),
            }
            raise HTTPException(status_code=409, detail=detail)

        if existing_success:
            remote_status = await self._check_remote_bill_status(factura_data, known_bill_id=known_bill_id)
            if remote_status.get("exists") is True:
                await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "procesado"}))
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Factura ya fue causada previamente",
                        "code": "FACTURA_YA_CAUSADA",
                        "alegra_bill_id": remote_status.get("bill_id") or existing_success.get("alegra_bill_id"),
                    },
                )
            if remote_status.get("exists") is None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "No se pudo verificar en Alegra si la factura sigue causada. Intenta nuevamente.",
                        "code": "NO_VERIFICADO_ALEGRA",
                    },
                )

            await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "pendiente"}))
            factura_data["estado"] = "pendiente"

        overrides_map = overrides_map or {}

        missing_confirmation = []
        for item in factura_data.get("items_factura", []) or []:
            override = overrides_map.get(str(item.get("id")))
            cuenta_actual = item.get("cuenta_contable_alegra")
            cuenta_override = override.get("cuenta_contable_alegra") if override else None
            effective_cuenta = cuenta_override if cuenta_override is not None else cuenta_actual
            if not effective_cuenta:
                missing_confirmation.append(str(item.get("id")))

        if missing_confirmation:
            try:
                await provider_mapping_service.compute_and_save_mapping(
                    factura_data.get("nit_proveedor"), factura_data.get("nombre_proveedor")
                )
                refreshed = await run_in_executor(lambda: get_factura_with_items(factura_id))
                if refreshed:
                    factura_data = refreshed
            except Exception:
                pass

            missing_confirmation = []
            for item in factura_data.get("items_factura", []) or []:
                override = overrides_map.get(str(item.get("id")))
                cuenta_actual = item.get("cuenta_contable_alegra")
                cuenta_override = override.get("cuenta_contable_alegra") if override else None
                effective_cuenta = cuenta_override if cuenta_override is not None else cuenta_actual
                if not effective_cuenta:
                    missing_confirmation.append(str(item.get("id")))

            if missing_confirmation:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Factura en revision manual: confirma cuenta por item antes de causar",
                        "code": "REQUIERE_CONFIRMACION_MANUAL",
                        "missing_item_ids": missing_confirmation,
                    },
                )

        resolved_name = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                provider_contact = await alegra_service.resolve_provider_contact(
                    client,
                    factura_data.get("nit_proveedor"),
                    factura_data.get("nombre_proveedor") or "Proveedor Generico",
                )
            if isinstance(provider_contact, dict):
                candidate_name = (provider_contact.get("name") or "").strip()
                if candidate_name:
                    resolved_name = candidate_name
        except Exception:
            resolved_name = None

        if resolved_name and resolved_name != (factura_data.get("nombre_proveedor") or ""):
            await run_in_executor(lambda: update_factura_fields(factura_id, {"nombre_proveedor": resolved_name}))
            factura_data["nombre_proveedor"] = resolved_name

        items = []
        for item in factura_data.get("items_factura", []) or []:
            override = overrides_map.get(str(item.get("id")))
            cuenta_contable = item.get("cuenta_contable_alegra")
            centro_costo = item.get("centro_costo_alegra")

            if override:
                if override.get("cuenta_contable_alegra") is not None:
                    cuenta_contable = override.get("cuenta_contable_alegra")
                if override.get("centro_costo_alegra") is not None:
                    centro_costo = override.get("centro_costo_alegra")

                await run_in_executor(
                    lambda: update_item_fields(
                        item.get("id"),
                        {
                            "cuenta_contable_alegra": cuenta_contable,
                            "centro_costo_alegra": centro_costo,
                        },
                    )
                )

            items.append(
                FacturaItem(
                    descripcion=item.get("descripcion", ""),
                    cantidad=item.get("cantidad", 0),
                    precio_unitario=item.get("precio_unitario", 0),
                    descuento=item.get("descuento", 0),
                    iva_porcentaje=item.get("iva_porcentaje", 19),
                    total_linea=item.get("total_linea", 0),
                    cuenta_contable_alegra=cuenta_contable,
                    centro_costo_alegra=centro_costo,
                )
            )

        factura_model = FacturaDIAN(
            cufe=factura_data.get("cufe"),
            numero_factura=factura_data.get("numero_factura"),
            fecha_emision=date_parser.parse(factura_data.get("fecha_emision") or factura_data.get("created_at")),
            fecha_vencimiento=date_parser.parse(factura_data["fecha_vencimiento"]) if factura_data.get("fecha_vencimiento") else None,
            nit_proveedor=factura_data.get("nit_proveedor"),
            nombre_proveedor=factura_data.get("nombre_proveedor"),
            nit_receptor=factura_data.get("nit_receptor"),
            subtotal=factura_data.get("subtotal", 0),
            iva=factura_data.get("iva", 0),
            rete_fuente=factura_data.get("rete_fuente", 0),
            rete_ica=factura_data.get("rete_ica", 0),
            rete_iva=factura_data.get("rete_iva", 0),
            total=factura_data.get("total", 0),
            moneda=factura_data.get("moneda") or "COP",
            xml_raw=factura_data.get("xml_raw"),
            items=items,
        )

        try:
            alegra_response = await alegra_service.crear_bill(factura_model)
            await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "procesado"}))
            try:
                await run_in_executor(
                    lambda: save_causacion(
                        {
                            "factura_id": factura_id,
                            "alegra_bill_id": alegra_response.get("id"),
                            "alegra_response": alegra_response,
                            "estado": "exitoso",
                            "intentos": 1,
                            "error_msg": None,
                        }
                    )
                )
            except Exception as log_exc:
                logger.error("causacion_log_error", extra={"factura_id": factura_id, "error": str(log_exc)})
            return alegra_response
        except AlegraDuplicateBillError as exc:
            await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "procesado"}))
            try:
                await run_in_executor(
                    lambda: save_causacion(
                        {
                            "factura_id": factura_id,
                            "alegra_bill_id": None,
                            "alegra_response": {"error": str(exc), "code": "DUPLICADO_ALEGRA"},
                            "estado": "fallido",
                            "intentos": 1,
                            "error_msg": str(exc),
                        }
                    )
                )
            except Exception as log_exc:
                logger.error("causacion_log_error", extra={"factura_id": factura_id, "error": str(log_exc)})
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "code": "DUPLICADO_ALEGRA",
                    "alegra_bill_id": None,
                },
            )
        except Exception as exc:
            error_text = str(exc).strip() or repr(exc)
            await run_in_executor(lambda: update_factura_fields(factura_id, {"estado": "error"}))
            try:
                await run_in_executor(
                    lambda: save_causacion(
                        {
                            "factura_id": factura_id,
                            "alegra_bill_id": None,
                            "alegra_response": {"error": error_text},
                            "estado": "fallido",
                            "intentos": 1,
                            "error_msg": error_text,
                        }
                    )
                )
            except Exception as log_exc:
                logger.error("causacion_log_error", extra={"factura_id": factura_id, "error": str(log_exc)})
            logger.error("causacion_error", extra={"factura_id": factura_id, "error": error_text})
            raise HTTPException(status_code=502, detail=error_text)


factura_service = FacturaService()
