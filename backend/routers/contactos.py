from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
import re
from services.alegra_service import alegra_service

router = APIRouter(prefix="/contactos", tags=["contactos"])


class ContactPayload(BaseModel):
    name: str = Field(..., min_length=2)
    identification: str | None = None
    identification_type: str | None = None
    dv: str | None = None
    kind_of_person: str | None = None
    regime: str | None = None
    department: str | None = None
    city: str | None = None
    address: str | None = None
    country: str | None = None
    email: str | None = None
    phone_primary: str | None = None
    mobile: str | None = None
    contact_type: list[str] | None = None
    status: str | None = None


def _error_message(exc: Exception, fallback: str) -> str:
    message = str(exc).strip()
    return message or fallback


def _normalize_contact(contact: dict) -> dict:
    raw_type = contact.get("type")
    if isinstance(raw_type, list):
        contact_type = raw_type
    elif isinstance(raw_type, str) and raw_type.strip():
        contact_type = [raw_type]
    else:
        contact_type = []

    identification_object = contact.get("identificationObject") or {}
    address = contact.get("address") or {}

    return {
        "id": contact.get("id"),
        "name": contact.get("name"),
        "identification": contact.get("identification"),
        "identification_type": identification_object.get("type") or "NIT",
        "dv": identification_object.get("dv") or "",
        "kind_of_person": contact.get("kindOfPerson") or "LEGAL_ENTITY",
        "regime": contact.get("regime") or "COMMON_REGIME",
        "department": address.get("department") or "",
        "city": address.get("city") or "",
        "address": address.get("address") or "",
        "country": address.get("country") or "Colombia",
        "email": contact.get("email"),
        "phone_primary": contact.get("phonePrimary") or contact.get("phone_primary"),
        "mobile": contact.get("mobile"),
        "status": contact.get("status") or "active",
        "type": contact_type,
    }


def _to_alegra_payload(payload: ContactPayload) -> dict:
    data = {
        "name": payload.name,
        "type": payload.contact_type or ["provider"],
    }

    if payload.identification:
        data["identification"] = payload.identification
        data["identificationObject"] = {
            "type": payload.identification_type or "NIT",
            "number": payload.identification,
            "dv": payload.dv or "",
        }
    if payload.kind_of_person:
        data["kindOfPerson"] = payload.kind_of_person
    if payload.regime:
        data["regime"] = payload.regime
    if payload.email:
        data["email"] = payload.email
    if payload.phone_primary:
        data["phonePrimary"] = payload.phone_primary
    if payload.mobile:
        data["mobile"] = payload.mobile
    if payload.status:
        data["status"] = payload.status

    address_payload = {
        "city": payload.city or "",
        "department": payload.department or "",
        "country": payload.country or "Colombia",
        "address": payload.address or "",
    }
    if any(value for value in address_payload.values()):
        data["address"] = address_payload

    return data


@router.get("/")
async def list_contactos(
    tipo: str | None = Query("all"),
    estado: str | None = Query("all"),
    search: str | None = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=30),
):
    type_map = {
        "all": None,
        "provider": "provider",
        "client": "client",
    }
    resolved_type = type_map.get((tipo or "all").lower())
    if (tipo or "all").lower() not in type_map:
        raise HTTPException(status_code=400, detail="Tipo invalido. Usa: all, provider o client.")

    start = (page - 1) * page_size

    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            contacts = await alegra_service.list_contacts(
                client,
                resolved_type,
                start=start,
                limit=page_size,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_message(exc, "No se pudo consultar contactos en Alegra."),
        ) from exc

    normalized = [_normalize_contact(item) for item in contacts]

    if estado and estado != "all":
        normalized = [item for item in normalized if item.get("status") == estado]

    if search:
        term = search.lower().strip()
        numeric_term = re.sub(r"\D", "", term)

        # If the user searches by NIT/identification, run an exact API lookup
        # independent of current pagination so existing contacts are not missed.
        if numeric_term:
            try:
                async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                    by_identification = await alegra_service.list_contacts(
                        client,
                        resolved_type,
                        start=0,
                        limit=30,
                        identification=numeric_term,
                    )
                for contact in by_identification:
                    item = _normalize_contact(contact)
                    item_id = str(item.get("id") or "")
                    if item_id and all(str(existing.get("id") or "") != item_id for existing in normalized):
                        normalized.append(item)
            except Exception:
                # Keep regular filtering path if direct identification lookup fails.
                pass

        normalized = [
            item for item in normalized
            if term in (item.get("name") or "").lower()
            or term in (item.get("identification") or "").lower()
            or term in (item.get("email") or "").lower()
            or term in (item.get("phone_primary") or "").lower()
            or term in (item.get("mobile") or "").lower()
            or (
                numeric_term
                and numeric_term in re.sub(r"\D", "", str(item.get("identification") or ""))
            )
        ]

    return {
        "data": normalized,
        "count": len(normalized),
        "page": page,
        "page_size": page_size,
        "has_more": len(contacts) == page_size,
    }


@router.get("/{contact_id}")
async def get_contacto(contact_id: str):
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            data = await alegra_service.get_contact(client, contact_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_message(exc, "No se pudo consultar el contacto en Alegra."),
        ) from exc

    return _normalize_contact(data)


@router.post("/")
async def create_contacto(payload: ContactPayload):
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            data = await alegra_service.create_contact(client, _to_alegra_payload(payload))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_message(exc, "No se pudo crear el contacto en Alegra."),
        ) from exc

    return _normalize_contact(data)


@router.patch("/{contact_id}")
async def update_contacto(contact_id: str, payload: ContactPayload):
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            data = await alegra_service.update_contact(client, contact_id, _to_alegra_payload(payload))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_message(exc, "No se pudo actualizar el contacto en Alegra."),
        ) from exc

    return _normalize_contact(data)


@router.delete("/{contact_id}")
async def delete_contacto(contact_id: str):
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            await alegra_service.delete_contact(client, contact_id)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_message(exc, "No se pudo eliminar el contacto en Alegra."),
        ) from exc

    return {"status": "deleted", "id": contact_id}
