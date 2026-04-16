from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from services.factura_service import factura_service
from services.pdf_extraction_service import PdfExtractionError, extraer_pdf_from_bytes
from services.pdf_ingestion_service import pdf_ingestion_service

router = APIRouter(prefix="/facturas", tags=["facturas"])


class ItemOverride(BaseModel):
    item_id: str
    cuenta_contable_alegra: str | None = None
    centro_costo_alegra: str | None = None


class CausarFacturaRequest(BaseModel):
    item_overrides: list[ItemOverride] = []


class PdfFacturaItem(BaseModel):
    descripcion: str = ""
    cantidad: float = 0
    precio_unitario: float = 0
    descuento: float = 0
    iva_porcentaje: float = 0
    total_linea: float = 0
    cuenta_contable_alegra: str | None = None
    centro_costo_alegra: str | None = None


class PdfFacturaPayload(BaseModel):
    cufe: str | None = None
    numero_factura: str | None = None
    fecha_emision: str | None = None
    fecha_vencimiento: str | None = None
    nit_proveedor: str | None = None
    nombre_proveedor: str | None = None
    nit_receptor: str | None = None
    subtotal: float = 0
    iva: float = 0
    rete_fuente: float = 0
    rete_ica: float = 0
    rete_iva: float = 0
    total: float = 0
    moneda: str = "COP"
    items: list[PdfFacturaItem] = Field(default_factory=list)


class PdfConfirmRequest(BaseModel):
    facturas: list[PdfFacturaPayload] = Field(default_factory=list)
    apply_ai: bool = True
    auto_apply_ai: bool = False


@router.post("/preview-upload")
async def preview_upload_facturas(
    files: list[UploadFile] = File(...), apply_ai: bool = True, auto_apply_ai: bool = False
):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un archivo XML o ZIP.")
    return await factura_service.preview_upload_facturas(
        files, apply_ai=apply_ai, auto_apply_ai=auto_apply_ai
    )


@router.post("/upload")
async def upload_facturas(
    files: list[UploadFile] = File(...), apply_ai: bool = True, auto_apply_ai: bool = False
):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un archivo XML o ZIP.")
    return await factura_service.upload_facturas(
        files, apply_ai=apply_ai, auto_apply_ai=auto_apply_ai
    )

@router.post("/extraer-pdf")
async def extraer_pdf(file: UploadFile = File(...), preview: bool = True):
    if not file:
        raise HTTPException(status_code=400, detail="Debes subir un archivo PDF.")
    filename = file.filename or "sin_nombre.pdf"
    try:
        content = await file.read()
        return await extraer_pdf_from_bytes(filename, content, preview=preview)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/preview-pdf")
async def preview_pdf(payload: PdfConfirmRequest):
    if not payload.facturas:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una factura.")

    results = []
    for factura in payload.facturas:
        results.append(
            await pdf_ingestion_service.process_factura_payload(
                factura.model_dump(),
                persist=False,
                apply_ai=payload.apply_ai,
                auto_apply_ai=payload.auto_apply_ai,
            )
        )

    summary = {
        "total": len(results),
        "valid": len([r for r in results if r.get("status") == "valid"]),
        "duplicates": len([r for r in results if r.get("status") == "duplicate"]),
        "errors": len([r for r in results if r.get("status") == "error"]),
    }

    return {
        "summary": summary,
        "facturas": results,
    }


@router.post("/confirmar-pdf")
async def confirmar_pdf(payload: PdfConfirmRequest):
    if not payload.facturas:
        raise HTTPException(status_code=400, detail="Debes enviar al menos una factura.")

    results = []
    for factura in payload.facturas:
        results.append(
            await pdf_ingestion_service.process_factura_payload(
                factura.model_dump(),
                persist=True,
                apply_ai=payload.apply_ai,
                auto_apply_ai=payload.auto_apply_ai,
            )
        )

    summary = {
        "total": len(results),
        "created": len([r for r in results if r.get("status") == "created"]),
        "duplicates": len([r for r in results if r.get("status") == "duplicate"]),
        "errors": len([r for r in results if r.get("status") == "error"]),
    }

    return {
        "summary": summary,
        "facturas": results,
    }

@router.get("/stats")
async def get_facturas_stats():
    return await factura_service.get_facturas_stats()

@router.get("/")
async def get_facturas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    estado: str | None = None,
    proveedor: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
):
    return await factura_service.get_facturas(
        page=page,
        page_size=page_size,
        estado=estado,
        proveedor=proveedor,
        desde=desde,
        hasta=hasta,
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    return await factura_service.get_job_status(job_id)


@router.post("/{factura_id}/causar-async", status_code=202)
async def causar_factura_async(factura_id: str, payload: CausarFacturaRequest | None = None):
    overrides_map = {}
    if payload and payload.item_overrides:
        for item in payload.item_overrides:
            overrides_map[str(item.item_id)] = {
                "cuenta_contable_alegra": item.cuenta_contable_alegra,
                "centro_costo_alegra": item.centro_costo_alegra,
            }
    return await factura_service.enqueue_causar_factura(factura_id, overrides_map)

@router.get("/{factura_id}")
async def get_factura(factura_id: str):
    return await factura_service.get_factura(factura_id)

@router.post("/{factura_id}/causar")
async def causar_factura(factura_id: str, payload: CausarFacturaRequest | None = None):
    overrides_map = {}
    if payload and payload.item_overrides:
        for item in payload.item_overrides:
            overrides_map[str(item.item_id)] = {
                "cuenta_contable_alegra": item.cuenta_contable_alegra,
                "centro_costo_alegra": item.centro_costo_alegra,
            }

    return await factura_service.causar_factura(factura_id, overrides_map)
