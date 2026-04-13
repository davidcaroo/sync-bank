from fastapi import APIRouter, HTTPException, Query
import httpx
from repositories.config_repository import (
    list_config_cuentas as repo_list_config_cuentas,
    create_config_cuenta as repo_create_config_cuenta,
    update_config_cuenta as repo_update_config_cuenta,
    delete_config_cuenta as repo_delete_config_cuenta,
)
from repositories.db_utils import run_in_executor
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
    return await run_in_executor(lambda: repo_list_config_cuentas(activo=activo))

@router.post("/")
async def create_config_cuenta(payload: dict):
    created = await run_in_executor(lambda: repo_create_config_cuenta(payload))
    if not created:
        raise HTTPException(status_code=400, detail="No se pudo crear el registro")
    return created

@router.patch("/{config_id}")
async def update_config_cuenta(config_id: str, payload: dict):
    updated = await run_in_executor(lambda: repo_update_config_cuenta(config_id, payload))
    if not updated:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return updated

@router.delete("/{config_id}")
async def delete_config_cuenta(config_id: str):
    deleted = await run_in_executor(lambda: repo_delete_config_cuenta(config_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"status": "deleted"}
