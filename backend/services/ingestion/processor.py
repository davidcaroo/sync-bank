from config import settings
from services.ai_service import clasificar_item


class IngestionProcessor:
    def __init__(
        self,
        *,
        parse_xml,
        run_in_executor,
        get_config_cuenta,
        sync_config_proveedor_nombre,
        find_factura_by_cufe,
        save_factura,
    ) -> None:
        self._parse_xml = parse_xml
        self._run_in_executor = run_in_executor
        self._get_config_cuenta = get_config_cuenta
        self._sync_config_proveedor_nombre = sync_config_proveedor_nombre
        self._find_factura_by_cufe = find_factura_by_cufe
        self._save_factura = save_factura

    async def process_xml_document(
        self,
        xml_doc,
        *,
        persist: bool,
        apply_ai: bool,
        categories: list | None,
        cost_centers: list | None,
        auto_apply_ai: bool = False,
        preview_mode: bool = False,
    ) -> dict:
        try:
            factura = self._parse_xml(xml_doc.xml_text)
        except Exception as exc:
            return {
                "file_name": xml_doc.file_name,
                "entry_name": xml_doc.entry_name,
                "status": "invalid",
                "reason": f"Error de parser XML: {exc}",
            }

        if persist:
            await self._run_in_executor(
                lambda: self._sync_config_proveedor_nombre(factura.nit_proveedor, factura.nombre_proveedor)
            )

        prefilled_items = []
        preview_items = []
        ai_cache = {}

        config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))
        historical_hint = None

        if not config:
            try:
                from services.provider_mapping_service import provider_mapping_service

                if preview_mode:
                    # Keep preview fast: use local historical hint only.
                    historical_hint = await provider_mapping_service.suggest_mapping_from_history(
                        factura.nit_proveedor,
                        min_occurrences=2,
                        min_share=0.6,
                    )
                else:
                    await provider_mapping_service.compute_and_save_mapping(
                        factura.nit_proveedor, factura.nombre_proveedor
                    )
                    config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))
                    if not config:
                        historical_hint = await provider_mapping_service.suggest_mapping_from_history(
                            factura.nit_proveedor,
                            min_occurrences=2,
                            min_share=0.6,
                        )
            except Exception:
                config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))

        for item in factura.items:
            prefill_source = "none"
            confidence = None
            suggested_cuenta = None
            suggested_centro = None

            cuenta_to_save = None
            centro_to_save = None

            if config:
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

            # Build preview item (contains suggestions and confidence)
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

            # Build saved item payload (only include allowed keys)
            save_item = {
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

            prefilled_items.append(save_item)

        duplicate = bool(await self._run_in_executor(lambda: self._find_factura_by_cufe(factura.cufe))) if factura.cufe else False

        factura_preview = {
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

        if not persist:
            return {
                "file_name": xml_doc.file_name,
                "entry_name": xml_doc.entry_name,
                "status": "duplicate" if duplicate else "valid",
                "reason": "CUFE ya existe" if duplicate else None,
                "factura_preview": factura_preview,
            }

        factura_payload = factura.model_dump(exclude={"items"}, mode="json")
        factura_payload["estado"] = "pendiente"

        try:
            save_result = await self._run_in_executor(
                lambda: self._save_factura(
                    factura_payload,
                    prefilled_items,
                )
            )
        except Exception as exc:
            return {
                "file_name": xml_doc.file_name,
                "entry_name": xml_doc.entry_name,
                "status": "error",
                "reason": f"Error guardando factura: {exc}",
                "factura_id": None,
                "cufe": factura.cufe,
                "numero_factura": factura.numero_factura,
                "nit_proveedor": factura.nit_proveedor,
                "nombre_proveedor": factura.nombre_proveedor,
                "estado": "error",
            }

        is_duplicate = bool(save_result.get("duplicado"))
        return {
            "file_name": xml_doc.file_name,
            "entry_name": xml_doc.entry_name,
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