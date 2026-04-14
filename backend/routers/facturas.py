from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from services.factura_service import factura_service

router = APIRouter(prefix="/facturas", tags=["facturas"])


class ItemOverride(BaseModel):
    item_id: str
    cuenta_contable_alegra: str | None = None
    centro_costo_alegra: str | None = None


class CausarFacturaRequest(BaseModel):
    item_overrides: list[ItemOverride] = []


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
