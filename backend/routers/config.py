from fastapi import APIRouter, HTTPException, Query
import httpx
from services.supabase_service import supabase
from services.alegra_service import alegra_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/alegra/catalogo")
async def get_alegra_catalogo(refresh: bool = Query(False)):
    if refresh:
        alegra_service._categories = None
        alegra_service._cost_centers = None

    async with httpx.AsyncClient() as client:
        categories = await alegra_service.get_categories(client)
        cost_centers = await alegra_service.get_cost_centers(client)

    return {
        "categories": categories or [],
        "cost_centers": cost_centers or [],
    }


@router.get("/alegra/proveedor/resolve")
async def resolve_alegra_provider(
    nit: str = Query(..., min_length=3),
    nombre: str = Query(..., min_length=2),
):
    async with httpx.AsyncClient() as client:
        provider_id = await alegra_service.get_provider_id(client, nit, nombre)
    return {
        "provider_id": provider_id,
        "nit": nit,
        "nombre": nombre,
    }

@router.get("/")
async def list_config_cuentas(activo: bool | None = None):
    query = supabase.table("config_cuentas").select("*")
    if activo is not None:
        query = query.eq("activo", activo)
    res = query.order("created_at", desc=True).execute()
    return res.data or []

@router.post("/")
async def create_config_cuenta(payload: dict):
    res = supabase.table("config_cuentas").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="No se pudo crear el registro")
    return res.data[0]

@router.patch("/{config_id}")
async def update_config_cuenta(config_id: str, payload: dict):
    res = supabase.table("config_cuentas").update(payload).eq("id", config_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return res.data[0]

@router.delete("/{config_id}")
async def delete_config_cuenta(config_id: str):
    res = supabase.table("config_cuentas").delete().eq("id", config_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"status": "deleted"}
