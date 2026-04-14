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

        await self._run_in_executor(
            lambda: self._sync_config_proveedor_nombre(factura.nit_proveedor, factura.nombre_proveedor)
        )

        prefilled_items = []

        config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))

        if not config:
            try:
                from services.provider_mapping_service import provider_mapping_service

                await provider_mapping_service.compute_and_save_mapping(
                    factura.nit_proveedor, factura.nombre_proveedor
                )
                config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))
            except Exception:
                config = await self._run_in_executor(lambda: self._get_config_cuenta(factura.nit_proveedor))

        for item in factura.items:
            prefill_source = "none"
            confidence = 0.0

            if config:
                item.cuenta_contable_alegra = config["id_cuenta_alegra"]
                item.centro_costo_alegra = config.get("id_centro_costo_alegra")
                prefill_source = "config"
            elif apply_ai:
                classification = await clasificar_item(item.descripcion, categories or [], cost_centers or [])
                confidence = float(classification.get("confianza") or 0.0)
                if confidence < settings.AI_CONFIDENCE_THRESHOLD:
                    item.cuenta_contable_alegra = None
                    item.centro_costo_alegra = None
                    prefill_source = "none"
                else:
                    item.cuenta_contable_alegra = classification.get("cuenta_id")
                    item.centro_costo_alegra = classification.get("centro_costo_id")
                    prefill_source = "ai"

            prefilled_items.append(
                {
                    "descripcion": item.descripcion,
                    "cantidad": item.cantidad,
                    "precio_unitario": item.precio_unitario,
                    "descuento": item.descuento,
                    "iva_porcentaje": item.iva_porcentaje,
                    "total_linea": item.total_linea,
                    "cuenta_contable_alegra": item.cuenta_contable_alegra,
                    "centro_costo_alegra": item.centro_costo_alegra,
                    "prefill_source": prefill_source,
                    "confidence": confidence,
                }
            )

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
            "items": prefilled_items,
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
        }