import io
import zipfile
from dataclasses import dataclass

import httpx

from config import settings
from services.ai_service import clasificar_item
from services.alegra_service import alegra_service
from services.supabase_service import (
    find_factura_by_cufe,
    get_config_cuenta,
    save_factura,
    sync_config_proveedor_nombre,
)
from services.xml_parser import parse_xml_dian


@dataclass
class XMLDocument:
    file_name: str
    entry_name: str
    xml_text: str


class IngestionService:
    async def extract_xml_documents_from_upload(self, files) -> list[dict]:
        documents: list[XMLDocument] = []
        errors: list[dict] = []

        for file in files or []:
            filename = file.filename or "sin_nombre"
            lower_name = filename.lower()

            try:
                content = await file.read()
            except Exception as exc:
                errors.append(
                    {
                        "file_name": filename,
                        "entry_name": filename,
                        "status": "invalid",
                        "reason": f"No se pudo leer archivo: {exc}",
                    }
                )
                continue

            extracted = self.extract_xml_documents_from_attachment(filename, content)
            documents.extend(extracted.get("documents") or [])
            errors.extend(extracted.get("errors") or [])

        return {
            "documents": documents,
            "errors": errors,
        }

    def extract_xml_documents_from_attachment(self, file_name: str, content: bytes) -> dict:
        name = file_name or "sin_nombre"
        lower_name = name.lower()

        if lower_name.endswith(".xml"):
            xml_text = self._decode_xml_bytes(content)
            if xml_text is None:
                return {
                    "documents": [],
                    "errors": [
                        {
                            "file_name": name,
                            "entry_name": name,
                            "status": "invalid",
                            "reason": "No se pudo decodificar XML.",
                        }
                    ],
                }
            return {
                "documents": [XMLDocument(file_name=name, entry_name=name, xml_text=xml_text)],
                "errors": [],
            }

        if lower_name.endswith(".zip"):
            docs, errs = self._extract_xml_from_zip_bytes(name, content, path=name, depth=0)
            if not docs and not errs:
                errs.append(
                    {
                        "file_name": name,
                        "entry_name": name,
                        "status": "invalid",
                        "reason": "ZIP sin XML procesables.",
                    }
                )
            return {
                "documents": docs,
                "errors": errs,
            }

        return {
            "documents": [],
            "errors": [
                {
                    "file_name": name,
                    "entry_name": name,
                    "status": "invalid",
                    "reason": "Tipo de archivo no soportado. Solo .xml y .zip",
                }
            ],
        }

    async def process_xml_document(
        self,
        xml_doc: XMLDocument,
        *,
        persist: bool,
        apply_ai: bool,
        categories: list | None,
        cost_centers: list | None,
    ) -> dict:
        try:
            factura = parse_xml_dian(xml_doc.xml_text)
        except Exception as exc:
            return {
                "file_name": xml_doc.file_name,
                "entry_name": xml_doc.entry_name,
                "status": "invalid",
                "reason": f"Error de parser XML: {exc}",
            }

        sync_config_proveedor_nombre(factura.nit_proveedor, factura.nombre_proveedor)

        prefilled_items = []
        config = get_config_cuenta(factura.nit_proveedor)

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

        duplicate = bool(find_factura_by_cufe(factura.cufe)) if factura.cufe else False

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
            "total_retenciones": float(factura.rete_fuente or 0) + float(factura.rete_ica or 0) + float(factura.rete_iva or 0),
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
            save_result = save_factura(
                factura_payload,
                [i.model_dump(mode="json") for i in factura.items],
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

    async def build_prefill_context(self, *, apply_ai: bool) -> dict:
        if not apply_ai:
            return {"categories": [], "cost_centers": []}

        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            categories = await alegra_service.get_categories(client)
            cost_centers = await alegra_service.get_cost_centers(client)

        return {
            "categories": categories or [],
            "cost_centers": cost_centers or [],
        }

    def _extract_xml_from_zip_bytes(
        self,
        zip_name: str,
        content: bytes,
        *,
        path: str,
        depth: int,
    ) -> tuple[list[XMLDocument], list[dict]]:
        documents: list[XMLDocument] = []
        errors: list[dict] = []

        if depth > 3:
            return documents, [
                {
                    "file_name": zip_name,
                    "entry_name": path,
                    "status": "invalid",
                    "reason": "ZIP anidado demasiado profundo.",
                }
            ]

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zipped:
                for entry_name in zipped.namelist():
                    lower_entry = entry_name.lower()
                    try:
                        entry_bytes = zipped.read(entry_name)
                        nested_path = f"{path}/{entry_name}"

                        if lower_entry.endswith(".xml"):
                            xml_text = self._decode_xml_bytes(entry_bytes)
                            if xml_text is None:
                                errors.append(
                                    {
                                        "file_name": zip_name,
                                        "entry_name": nested_path,
                                        "status": "invalid",
                                        "reason": "No se pudo decodificar XML dentro del ZIP.",
                                    }
                                )
                                continue
                            documents.append(XMLDocument(file_name=zip_name, entry_name=nested_path, xml_text=xml_text))
                            continue

                        if lower_entry.endswith(".zip"):
                            nested_docs, nested_errors = self._extract_xml_from_zip_bytes(
                                zip_name,
                                entry_bytes,
                                path=nested_path,
                                depth=depth + 1,
                            )
                            documents.extend(nested_docs)
                            errors.extend(nested_errors)
                    except Exception as exc:
                        errors.append(
                            {
                                "file_name": zip_name,
                                "entry_name": f"{path}/{entry_name}",
                                "status": "invalid",
                                "reason": f"Error leyendo XML dentro de ZIP: {exc}",
                            }
                        )
        except Exception as exc:
            errors.append(
                {
                    "file_name": zip_name,
                    "entry_name": path,
                    "status": "invalid",
                    "reason": f"ZIP invalido: {exc}",
                }
            )

        return documents, errors

    def _decode_xml_bytes(self, content: bytes) -> str | None:
        for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
            try:
                return content.decode(encoding)
            except Exception:
                continue
        return None


ingestion_service = IngestionService()
