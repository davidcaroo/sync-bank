from __future__ import annotations

import logging
from typing import Any

from dateutil import parser as date_parser

from config import settings
from models.factura import FacturaDIAN, FacturaItem
from repositories.config_repository import get_config_cuenta, sync_config_proveedor_nombre
from repositories.db_utils import run_in_executor
from repositories.factura_repository import find_factura_by_cufe, save_factura
from repositories.ingestion_adapters import SyncFacturaRepositoryAdapter, SyncProviderConfigRepositoryAdapter
from services.ai_service import clasificar_item
from services.ingestion.prefill import IngestionPrefill
from services.provider_mapping_service import provider_mapping_service

logger = logging.getLogger("pdf-ingestion")

class PdfIngestionService:
    def __init__(self) -> None:
        self._prefill = IngestionPrefill()
        self._factura_repository = SyncFacturaRepositoryAdapter(
            run_in_executor=run_in_executor,
            find_factura_by_cufe=find_factura_by_cufe,
            save_factura=save_factura,
        )
        self._provider_config_repository = SyncProviderConfigRepositoryAdapter(
            run_in_executor=run_in_executor,
            get_config_cuenta=get_config_cuenta,
            sync_config_proveedor_nombre=sync_config_proveedor_nombre,
        )

    def _parse_date(self, value: str | None):
        if not value:
            return None
        try:
            return date_parser.parse(value)
        except Exception:
            return None

    def _build_factura_model(self, payload: dict[str, Any]) -> FacturaDIAN:
        items_payload = payload.get("items") or []
        items: list[FacturaItem] = []
        for item in items_payload:
            items.append(
                FacturaItem(
                    descripcion=item.get("descripcion", ""),
                    cantidad=item.get("cantidad", 0),
                    precio_unitario=item.get("precio_unitario", 0),
                    descuento=item.get("descuento", 0),
                    iva_porcentaje=item.get("iva_porcentaje", 0),
                    total_linea=item.get("total_linea", 0),
                    cuenta_contable_alegra=item.get("cuenta_contable_alegra"),
                    centro_costo_alegra=item.get("centro_costo_alegra"),
                )
            )

        factura = FacturaDIAN(
            cufe=payload.get("cufe"),
            numero_factura=payload.get("numero_factura"),
            fecha_emision=self._parse_date(payload.get("fecha_emision")),
            fecha_vencimiento=self._parse_date(payload.get("fecha_vencimiento")),
            nit_proveedor=payload.get("nit_proveedor"),
            nombre_proveedor=payload.get("nombre_proveedor"),
            nit_receptor=payload.get("nit_receptor"),
            subtotal=payload.get("subtotal", 0),
            iva=payload.get("iva", 0),
            rete_fuente=payload.get("rete_fuente", 0),
            rete_ica=payload.get("rete_ica", 0),
            rete_iva=payload.get("rete_iva", 0),
            total=payload.get("total", 0),
            moneda=payload.get("moneda") or "COP",
            items=items,
        )
        return factura.normalize()

    async def _prefill_items(
        self,
        factura: FacturaDIAN,
        *,
        apply_ai: bool,
        auto_apply_ai: bool,
        categories: list | None,
        cost_centers: list | None,
        preview_mode: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        prefilled_items: list[dict[str, Any]] = []
        preview_items: list[dict[str, Any]] = []
        ai_cache: dict[str, dict[str, Any]] = {}

        config = await self._provider_config_repository.get_config_cuenta(factura.nit_proveedor)
        historical_hint = None

        if not config:
            try:
                if preview_mode:
                    historical_hint = await provider_mapping_service.suggest_mapping_from_history(
                        factura.nit_proveedor,
                        min_occurrences=2,
                        min_share=0.6,
                    )
                else:
                    await provider_mapping_service.compute_and_save_mapping(
                        factura.nit_proveedor, factura.nombre_proveedor
                    )
                    config = await self._provider_config_repository.get_config_cuenta(factura.nit_proveedor)
                    if not config:
                        historical_hint = await provider_mapping_service.suggest_mapping_from_history(
                            factura.nit_proveedor,
                            min_occurrences=2,
                            min_share=0.6,
                        )
            except Exception:
                config = await self._provider_config_repository.get_config_cuenta(factura.nit_proveedor)

        for item in factura.items:
            prefill_source = "none"
            confidence = None
            suggested_cuenta = None
            suggested_centro = None

            cuenta_to_save = item.cuenta_contable_alegra
            centro_to_save = item.centro_costo_alegra

            if cuenta_to_save or centro_to_save:
                prefill_source = "manual"
            elif config:
                cuenta_to_save = config.get("id_cuenta_alegra")
                centro_to_save = config.get("id_centro_costo_alegra")
                prefill_source = "config"
                try:
                    confidence = float(config.get("confianza") or 1.0)
                except Exception:
                    confidence = 1.0
            elif historical_hint and historical_hint.get("cuenta"):
                cuenta_to_save = historical_hint.get("cuenta")
                centro_to_save = None
                prefill_source = "historical"
                try:
                    confidence = float(historical_hint.get("confidence") or 0.0)
                except Exception:
                    confidence = 0.0
            elif apply_ai:
                desc_key = (item.descripcion or "").strip().lower()
                if desc_key in ai_cache:
                    classification = ai_cache[desc_key]
                else:
                    classification = await clasificar_item(item.descripcion, categories or [], cost_centers or [])
                    ai_cache[desc_key] = classification
                suggested_cuenta = classification.get("cuenta_id")
                suggested_centro = classification.get("centro_costo_id")
                try:
                    confidence = float(classification.get("confianza") or 0.0)
                except Exception:
                    confidence = 0.0

                if confidence is not None and confidence >= settings.AI_CONFIDENCE_THRESHOLD:
                    cuenta_to_save = suggested_cuenta
                    centro_to_save = suggested_centro
                    prefill_source = "ai"
                else:
                    if auto_apply_ai and (suggested_cuenta or suggested_centro):
                        cuenta_to_save = suggested_cuenta
                        centro_to_save = suggested_centro
                        prefill_source = "ai_auto"
                    else:
                        prefill_source = "ai_suggestion" if (suggested_cuenta or suggested_centro) else "none"

            preview_item = {
                "descripcion": item.descripcion,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "descuento": item.descuento,
                "iva_porcentaje": item.iva_porcentaje,
                "total_linea": item.total_linea,
                "cuenta_contable_alegra": cuenta_to_save,
                "centro_costo_alegra": centro_to_save,
                "prefill_source": prefill_source,
                "confidence": confidence,
            }

            if prefill_source == "ai_suggestion":
                preview_item["suggested_cuenta_contable_alegra"] = suggested_cuenta
                preview_item["suggested_centro_costo_alegra"] = suggested_centro

            preview_items.append(preview_item)

            prefilled_items.append(
                {
                    "descripcion": item.descripcion,
                    "cantidad": item.cantidad,
                    "precio_unitario": item.precio_unitario,
                    "descuento": item.descuento,
                    "iva_porcentaje": item.iva_porcentaje,
                    "total_linea": item.total_linea,
                    "cuenta_contable_alegra": cuenta_to_save,
                    "centro_costo_alegra": centro_to_save,
                    "prefill_source": prefill_source,
                    "confidence": confidence,
                }
            )

        return prefilled_items, preview_items

    def _build_factura_preview(self, factura: FacturaDIAN, preview_items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "cufe": factura.cufe,
            "numero_factura": factura.numero_factura,
            "fecha_emision": factura.fecha_emision.isoformat() if factura.fecha_emision else None,
            "nit_proveedor": factura.nit_proveedor,
            "nombre_proveedor": factura.nombre_proveedor,
            "subtotal": factura.subtotal,
            "iva": factura.iva,
            "rete_fuente": factura.rete_fuente,
            "rete_ica": factura.rete_ica,
            "rete_iva": factura.rete_iva,
            "total_bruto": float(factura.subtotal or 0) + float(factura.iva or 0),
            "total_retenciones": float(factura.rete_fuente or 0)
            + float(factura.rete_ica or 0)
            + float(factura.rete_iva or 0),
            "total_neto": factura.total,
            "total": factura.total,
            "moneda": factura.moneda,
            "items": preview_items,
        }

    async def process_factura_payload(
        self,
        payload: dict[str, Any],
        *,
        persist: bool,
        apply_ai: bool,
        auto_apply_ai: bool,
    ) -> dict[str, Any]:
        factura = self._build_factura_model(payload)
        duplicate = bool(await self._factura_repository.find_by_cufe(factura.cufe)) if factura.cufe else False

        prefill_context = await self._prefill.build_prefill_context(apply_ai=apply_ai)
        prefilled_items, preview_items = await self._prefill_items(
            factura,
            apply_ai=apply_ai,
            auto_apply_ai=auto_apply_ai,
            categories=prefill_context.get("categories"),
            cost_centers=prefill_context.get("cost_centers"),
            preview_mode=not persist,
        )

        factura_preview = self._build_factura_preview(factura, preview_items)

        if not persist:
            return {
                "status": "duplicate" if duplicate else "valid",
                "reason": "CUFE ya existe" if duplicate else None,
                "factura_preview": factura_preview,
            }

        await self._provider_config_repository.sync_proveedor_nombre(
            factura.nit_proveedor,
            factura.nombre_proveedor,
        )

        factura_payload = factura.model_dump(exclude={"items"}, mode="json")
        factura_payload["estado"] = "pendiente"

        try:
            save_result = await self._factura_repository.save_factura(factura_payload, prefilled_items)
        except Exception as exc:
            return {
                "status": "error",
                "reason": f"Error guardando factura: {exc}",
                "factura_id": None,
                "cufe": factura.cufe,
                "numero_factura": factura.numero_factura,
                "nit_proveedor": factura.nit_proveedor,
                "nombre_proveedor": factura.nombre_proveedor,
                "estado": "error",
                "factura_preview": factura_preview,
            }

        is_duplicate = bool(save_result.get("duplicado"))
        return {
            "status": "duplicate" if is_duplicate else "created",
            "reason": "CUFE ya existe" if is_duplicate else None,
            "factura_id": save_result.get("factura_id"),
            "cufe": factura.cufe,
            "numero_factura": factura.numero_factura,
            "nit_proveedor": factura.nit_proveedor,
            "nombre_proveedor": factura.nombre_proveedor,
            "estado": "duplicado" if is_duplicate else "pendiente",
            "factura_preview": factura_preview,
        }

pdf_ingestion_service = PdfIngestionService()
