from fastapi import APIRouter, HTTPException, Query
import httpx
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field, field_validator
from repositories.config_repository import (
    get_config_cuenta_by_id as repo_get_config_cuenta_by_id,
    list_config_cuentas as repo_list_config_cuentas,
    create_config_cuenta as repo_create_config_cuenta,
    update_config_cuenta as repo_update_config_cuenta,
    delete_config_cuenta as repo_delete_config_cuenta,
)
from repositories.db_utils import run_in_executor
from services.alegra_service import alegra_service
from services.provider_mapping.normalization import normalize_nit

router = APIRouter(prefix="/config", tags=["config"])

CLASSIFICATION_FIELDS = ("nit_proveedor", "id_cuenta_alegra", "id_centro_costo_alegra")


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
    return value or None


class ConfigCuentaCreate(BaseModel):
    nit_proveedor: str = Field(min_length=3)
    nombre_proveedor: str | None = None
    id_cuenta_alegra: str = Field(min_length=1)
    id_centro_costo_alegra: str | None = None
    auto_causar: bool = False
    activo: bool = True

    _clean = field_validator(
        "nombre_proveedor", "id_cuenta_alegra", "id_centro_costo_alegra", mode="before"
    )(_blank_to_none)


class ConfigCuentaUpdate(BaseModel):
    nit_proveedor: str | None = None
    nombre_proveedor: str | None = None
    id_cuenta_alegra: str | None = None
    id_centro_costo_alegra: str | None = None
    auto_causar: bool | None = None
    activo: bool | None = None

    _clean = field_validator(
        "nit_proveedor",
        "nombre_proveedor",
        "id_cuenta_alegra",
        "id_centro_costo_alegra",
        mode="before",
    )(_blank_to_none)


async def _persist(action):
    try:
        return await run_in_executor(action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=409, detail="Ya existe una regla para ese NIT."
        ) from exc


def _require_complete_for_auto_causar(rule: dict) -> None:
    if rule.get("auto_causar") and not (
        rule.get("id_cuenta_alegra") and rule.get("id_centro_costo_alegra")
    ):
        raise HTTPException(
            status_code=422,
            detail="La autocausación requiere cuenta y centro de costo.",
        )


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
async def create_config_cuenta(payload: ConfigCuentaCreate):
    rule = payload.model_dump()
    rule["nit_proveedor"] = normalize_nit(rule["nit_proveedor"])
    if not rule["nit_proveedor"]:
        raise HTTPException(status_code=422, detail="NIT invalido.")
    _require_complete_for_auto_causar(rule)
    rule.update(source="manual", confianza=1)

    created = await _persist(lambda: repo_create_config_cuenta(rule))
    if not created:
        raise HTTPException(status_code=400, detail="No se pudo crear el registro")
    return created


@router.patch("/{config_id}")
async def update_config_cuenta(config_id: str, payload: ConfigCuentaUpdate):
    current = await run_in_executor(lambda: repo_get_config_cuenta_by_id(config_id))
    if not current:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    changes = payload.model_dump(exclude_unset=True)
    if "nit_proveedor" in changes and changes["nit_proveedor"]:
        changes["nit_proveedor"] = normalize_nit(changes["nit_proveedor"])
    if "id_cuenta_alegra" in changes and not changes["id_cuenta_alegra"]:
        raise HTTPException(status_code=422, detail="La cuenta es obligatoria.")

    classification_changed = any(
        field in changes and changes[field] != current.get(field)
        for field in CLASSIFICATION_FIELDS
    )
    # Changing what the rule applies to revokes autocausation until the operator
    # explicitly grants it again.
    if classification_changed and changes.get("auto_causar") is not True:
        changes["auto_causar"] = False

    _require_complete_for_auto_causar({**current, **changes})
    # A human edit takes the rule out of automatic learning's reach.
    changes.update(source="manual", confianza=1)

    updated = await _persist(lambda: repo_update_config_cuenta(config_id, changes))
    if not updated:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return updated


@router.delete("/{config_id}")
async def delete_config_cuenta(config_id: str):
    deleted = await run_in_executor(lambda: repo_delete_config_cuenta(config_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"status": "deleted"}
