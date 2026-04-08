from fastapi import APIRouter, HTTPException, Query
from dateutil import parser as date_parser
from datetime import datetime
from pydantic import BaseModel
from services.supabase_service import supabase, save_causacion, get_successful_causacion
from services.alegra_service import alegra_service, AlegraDuplicateBillError
from models.factura import FacturaDIAN, FacturaItem

router = APIRouter(prefix="/facturas", tags=["facturas"])


class ItemOverride(BaseModel):
    item_id: str
    cuenta_contable_alegra: str | None = None
    centro_costo_alegra: str | None = None


class CausarFacturaRequest(BaseModel):
    item_overrides: list[ItemOverride] = []

@router.get("/stats")
async def get_facturas_stats():
    res = supabase.table("facturas").select("estado, created_at").execute()
    facturas = res.data or []
    hoy = 0
    causadas = 0
    pendientes = 0
    errores = 0
    today_str = datetime.utcnow().date().isoformat()

    for factura in facturas:
        created_at = factura.get("created_at")
        if created_at:
            created_date = date_parser.parse(created_at).date().isoformat()
            if created_date == today_str:
                hoy += 1

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
    return {
        "data": res.data or [],
        "count": res.count or 0,
        "page": page,
        "page_size": page_size,
    }

@router.get("/{factura_id}")
async def get_factura(factura_id: str):
    res = supabase.table("facturas").select("*, items_factura(*)").eq("id", factura_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return res.data

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
        save_causacion({
            "factura_id": factura_id,
            "alegra_bill_id": alegra_response.get("id"),
            "alegra_response": alegra_response,
            "estado": "exitoso",
            "intentos": 1,
            "error_msg": None,
        })
        return alegra_response
    except AlegraDuplicateBillError as exc:
        supabase.table("facturas").update({"estado": "duplicado"}).eq("id", factura_id).execute()
        save_causacion({
            "factura_id": factura_id,
            "alegra_bill_id": None,
            "alegra_response": {"error": str(exc), "code": "DUPLICADO_ALEGRA"},
            "estado": "duplicado",
            "intentos": 1,
            "error_msg": str(exc),
        })
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "code": "DUPLICADO_ALEGRA",
                "alegra_bill_id": None,
            },
        )
    except Exception as exc:
        supabase.table("facturas").update({"estado": "error"}).eq("id", factura_id).execute()
        save_causacion({
            "factura_id": factura_id,
            "alegra_bill_id": None,
            "alegra_response": {"error": str(exc)},
            "estado": "fallido",
            "intentos": 1,
            "error_msg": str(exc),
        })
        raise HTTPException(status_code=502, detail=str(exc))
