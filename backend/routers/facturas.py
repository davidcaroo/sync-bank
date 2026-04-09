from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from dateutil import parser as date_parser
from datetime import datetime
from pydantic import BaseModel
import httpx
from services.supabase_service import supabase, save_causacion, get_successful_causacion
from services.alegra_service import alegra_service, AlegraDuplicateBillError
from services.ingestion_service import ingestion_service
from services.timezone_service import BOGOTA_TZ, now_bogota, to_bogota
from services.xml_parser import parse_xml_dian
from models.factura import FacturaDIAN, FacturaItem

router = APIRouter(prefix="/facturas", tags=["facturas"])


class ItemOverride(BaseModel):
    item_id: str
    cuenta_contable_alegra: str | None = None
    centro_costo_alegra: str | None = None


class CausarFacturaRequest(BaseModel):
    item_overrides: list[ItemOverride] = []


async def _hydrate_items_from_alegra_if_needed(factura: dict) -> dict:
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

        # Only enrich empty fields to preserve manual overrides done locally.
        patch = {}
        if not current_cuenta and new_cuenta:
            patch["cuenta_contable_alegra"] = new_cuenta
        if not current_centro and new_centro:
            patch["centro_costo_alegra"] = new_centro

        if patch:
            try:
                supabase.table("items_factura").update(patch).eq("id", item.get("id")).execute()
            except Exception:
                continue

            item.update(patch)
            updated = True

    if updated:
        factura["items_factura"] = items

    if remote.get("bill_id"):
        factura["alegra_bill_id"] = remote.get("bill_id")

    return factura


def _enrich_factura_monetary_fields(factura: dict) -> dict:
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


def _preview_summary(results: list[dict], *, total_files: int, total_xml: int) -> dict:
    return {
        "total_files": total_files,
        "total_xml": total_xml,
        "valid": len([item for item in results if item.get("status") == "valid"]),
        "invalid": len([item for item in results if item.get("status") == "invalid"]),
        "duplicates": len([item for item in results if item.get("status") == "duplicate"]),
    }


def _upload_summary(results: list[dict], *, total_files: int, total_xml: int) -> dict:
    return {
        "total_files": total_files,
        "total_xml": total_xml,
        "created": len([item for item in results if item.get("status") == "created"]),
        "duplicates": len([item for item in results if item.get("status") == "duplicate"]),
        "errors": len([item for item in results if item.get("status") in {"error", "invalid"}]),
    }


@router.post("/preview-upload")
async def preview_upload_facturas(files: list[UploadFile] = File(...), apply_ai: bool = True):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un archivo XML o ZIP.")

    extracted = await ingestion_service.extract_xml_documents_from_upload(files)
    documents = extracted.get("documents") or []
    errors = extracted.get("errors") or []

    prefill_context = await ingestion_service.build_prefill_context(apply_ai=apply_ai)

    results = list(errors)
    for xml_doc in documents:
        result = await ingestion_service.process_xml_document(
            xml_doc,
            persist=False,
            apply_ai=apply_ai,
            categories=prefill_context.get("categories"),
            cost_centers=prefill_context.get("cost_centers"),
        )
        results.append(result)

    return {
        "summary": _preview_summary(
            results,
            total_files=len(files),
            total_xml=len(documents),
        ),
        "files": results,
    }


@router.post("/upload")
async def upload_facturas(files: list[UploadFile] = File(...), apply_ai: bool = True):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un archivo XML o ZIP.")

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
        )
        results.append(result)

    return {
        "summary": _upload_summary(
            results,
            total_files=len(files),
            total_xml=len(documents),
        ),
        "files": results,
    }

@router.get("/stats")
async def get_facturas_stats():
    res = supabase.table("facturas").select("estado, created_at").execute()
    facturas = res.data or []
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

@router.get("/")
async def get_facturas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    estado: str | None = None,
    proveedor: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
):
    query = supabase.table("facturas").select("*, items_factura(*)", count="exact")

    if estado:
        query = query.eq("estado", estado)
    if proveedor:
        query = query.ilike("nombre_proveedor", f"%{proveedor}%")
    if desde:
        query = query.gte("fecha_emision", desde)
    if hasta:
        query = query.lte("fecha_emision", hasta)

    start = (page - 1) * page_size
    end = start + page_size - 1

    res = query.order("created_at", desc=True).range(start, end).execute()
    rows = res.data or []
    rows = [_enrich_factura_monetary_fields(row) for row in rows]
    return {
        "data": rows,
        "count": res.count or 0,
        "page": page,
        "page_size": page_size,
    }

@router.get("/{factura_id}")
async def get_factura(factura_id: str):
    res = supabase.table("facturas").select("*, items_factura(*)").eq("id", factura_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    factura = await _hydrate_items_from_alegra_if_needed(res.data)
    return _enrich_factura_monetary_fields(factura)

@router.post("/{factura_id}/causar")
async def causar_factura(factura_id: str, payload: CausarFacturaRequest | None = None):
    res = supabase.table("facturas").select("*, items_factura(*)").eq("id", factura_id).single().execute()
    factura_data = res.data
    if not factura_data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if factura_data.get("estado") == "procesado":
        existing = get_successful_causacion(factura_id)
        detail = {
            "message": "Factura ya causada",
            "code": "FACTURA_YA_CAUSADA",
            "alegra_bill_id": existing.get("alegra_bill_id") if existing else None,
        }
        raise HTTPException(status_code=409, detail=detail)

    existing_success = get_successful_causacion(factura_id)
    if existing_success:
        supabase.table("facturas").update({"estado": "procesado"}).eq("id", factura_id).execute()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Factura ya fue causada previamente",
                "code": "FACTURA_YA_CAUSADA",
                "alegra_bill_id": existing_success.get("alegra_bill_id"),
            },
        )

    overrides_map = {}
    if payload and payload.item_overrides:
        for item in payload.item_overrides:
            overrides_map[str(item.item_id)] = item

    missing_confirmation = []
    for item in factura_data.get("items_factura", []) or []:
        override = overrides_map.get(str(item.get("id")))
        cuenta_actual = item.get("cuenta_contable_alegra")
        cuenta_override = override.cuenta_contable_alegra if override else None
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

    # Best-effort sync: if provider already exists in Alegra for this NIT,
    # persist the official contact name so UI and accounting views stay consistent.
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
        supabase.table("facturas").update({"nombre_proveedor": resolved_name}).eq("id", factura_id).execute()
        factura_data["nombre_proveedor"] = resolved_name

    items = []
    for item in factura_data.get("items_factura", []) or []:
        override = overrides_map.get(str(item.get("id")))
        cuenta_contable = item.get("cuenta_contable_alegra")
        centro_costo = item.get("centro_costo_alegra")

        if override:
            if override.cuenta_contable_alegra is not None:
                cuenta_contable = override.cuenta_contable_alegra
            if override.centro_costo_alegra is not None:
                centro_costo = override.centro_costo_alegra

            supabase.table("items_factura").update({
                "cuenta_contable_alegra": cuenta_contable,
                "centro_costo_alegra": centro_costo,
            }).eq("id", item.get("id")).execute()

        items.append(FacturaItem(
            descripcion=item.get("descripcion", ""),
            cantidad=item.get("cantidad", 0),
            precio_unitario=item.get("precio_unitario", 0),
            descuento=item.get("descuento", 0),
            iva_porcentaje=item.get("iva_porcentaje", 19),
            total_linea=item.get("total_linea", 0),
            cuenta_contable_alegra=cuenta_contable,
            centro_costo_alegra=centro_costo,
        ))

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
        supabase.table("facturas").update({"estado": "procesado"}).eq("id", factura_id).execute()
        try:
            save_causacion({
                "factura_id": factura_id,
                "alegra_bill_id": alegra_response.get("id"),
                "alegra_response": alegra_response,
                "estado": "exitoso",
                "intentos": 1,
                "error_msg": None,
            })
        except Exception as log_exc:
            print(f"No se pudo guardar log de causacion exitosa para factura {factura_id}: {log_exc}")
        return alegra_response
    except AlegraDuplicateBillError as exc:
        # If Alegra reports duplicate document, the bill already exists there.
        # Keep local invoice as processed to reflect business state in dashboard.
        supabase.table("facturas").update({"estado": "procesado"}).eq("id", factura_id).execute()
        try:
            save_causacion({
                "factura_id": factura_id,
                "alegra_bill_id": None,
                "alegra_response": {"error": str(exc), "code": "DUPLICADO_ALEGRA"},
                "estado": "fallido",
                "intentos": 1,
                "error_msg": str(exc),
            })
        except Exception as log_exc:
            print(f"No se pudo guardar log de causacion duplicada para factura {factura_id}: {log_exc}")
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
        supabase.table("facturas").update({"estado": "error"}).eq("id", factura_id).execute()
        try:
            save_causacion({
                "factura_id": factura_id,
                "alegra_bill_id": None,
                "alegra_response": {"error": error_text},
                "estado": "fallido",
                "intentos": 1,
                "error_msg": error_text,
            })
        except Exception as log_exc:
            print(f"No se pudo guardar log de causacion fallida para factura {factura_id}: {log_exc}")
        print(f"Error causando factura {factura_id}: {error_text}")
        raise HTTPException(status_code=502, detail=error_text)
