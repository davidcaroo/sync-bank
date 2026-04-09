import httpx
import base64
import re
from datetime import datetime
from config import settings
from models.factura import FacturaDIAN


class AlegraDuplicateBillError(Exception):
    pass


def _is_duplicate_bill_error(raw_error: str) -> bool:
    text = (raw_error or "").lower()
    duplicate_signals = [
        "already exists",
        "ya existe",
        "duplic",
        "documento repetido",
        "document number",
        "consecutivo",
    ]
    return any(signal in text for signal in duplicate_signals)


def _normalize_nit(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    return digits.lstrip("0") or digits


def _extract_contacts(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload.get("data")
        if isinstance(payload.get("results"), list):
            return payload.get("results")
    return []

class AlegraService:
    def __init__(self):
        auth_str = f"{settings.ALEGRA_EMAIL}:{settings.ALEGRA_TOKEN}"
        self.auth_header = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.alegra.com/api/v1"
        self._categories = None
        self._cost_centers = None

    def _flatten_categories(self, nodes):
        result = []

        def walk(node):
            if not isinstance(node, dict):
                return

            category_id = node.get("id")
            name = node.get("name") or node.get("text")
            code = node.get("code")
            status = node.get("status")

            if category_id and name and status != "inactive":
                result.append({
                    "id": category_id,
                    "name": name,
                    "code": code,
                    "type": node.get("type"),
                })

            children = node.get("children")
            if isinstance(children, list):
                for child in children:
                    walk(child)

        if isinstance(nodes, list):
            for node in nodes:
                walk(node)
        elif isinstance(nodes, dict):
            walk(nodes)

        dedup = {}
        for item in result:
            dedup[str(item["id"])] = item

        return list(dedup.values())

    async def get_categories(self, client: httpx.AsyncClient):
        if self._categories:
            return self._categories
        res = await client.get(f"{self.base_url}/categories?type=expense", headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            raw_categories = data.get("data", data) if isinstance(data, dict) else data
            self._categories = self._flatten_categories(raw_categories)
            return self._categories
        return []

    async def get_cost_centers(self, client: httpx.AsyncClient):
        if self._cost_centers:
            return self._cost_centers
        res = await client.get(f"{self.base_url}/cost-centers", headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            self._cost_centers = data.get("data", data) if isinstance(data, dict) else data
            return self._cost_centers
        return []

    async def list_contacts(
        self,
        client: httpx.AsyncClient,
        contact_type: str | None = "provider",
        start: int = 0,
        limit: int = 30,
        identification: str | None = None,
    ):
        params = {}
        if contact_type:
            params["type"] = contact_type
        if identification:
            params["identification"] = identification
        safe_limit = max(1, min(int(limit), 30))
        safe_start = max(0, int(start))
        params["start"] = safe_start
        params["limit"] = safe_limit

        res = await client.get(f"{self.base_url}/contacts", params=params, headers=self.headers)
        if res.status_code != 200:
            raise Exception(f"Error Alegra API al listar contactos: {res.text}")
        return _extract_contacts(res.json())

    async def get_contact(self, client: httpx.AsyncClient, contact_id: str):
        res = await client.get(f"{self.base_url}/contacts/{contact_id}", headers=self.headers)
        if res.status_code != 200:
            raise Exception(f"Error Alegra API al consultar contacto {contact_id}: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def create_contact(self, client: httpx.AsyncClient, payload: dict):
        res = await client.post(f"{self.base_url}/contacts", json=payload, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise Exception(f"Error Alegra API al crear contacto: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def update_contact(self, client: httpx.AsyncClient, contact_id: str, payload: dict):
        res = await client.put(f"{self.base_url}/contacts/{contact_id}", json=payload, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise Exception(f"Error Alegra API al actualizar contacto {contact_id}: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def delete_contact(self, client: httpx.AsyncClient, contact_id: str):
        res = await client.delete(f"{self.base_url}/contacts/{contact_id}", headers=self.headers)
        if res.status_code not in [200, 202, 204]:
            raise Exception(f"Error Alegra API al eliminar contacto {contact_id}: {res.text}")
        return True

    async def resolve_provider_contact(self, client: httpx.AsyncClient, nit: str, nombre: str) -> dict:
        normalized_nit = _normalize_nit(nit)

        async def find_by_identification(value: str | None):
            if not value:
                return None
            res = await client.get(
                f"{self.base_url}/contacts",
                params={"identification": value, "type": "provider"},
                headers=self.headers,
            )
            if res.status_code != 200:
                return None
            contacts = _extract_contacts(res.json())
            for contact in contacts:
                contact_id_number = _normalize_nit(str(contact.get("identification") or ""))
                if contact_id_number == _normalize_nit(value):
                    return contact
            if contacts:
                return contacts[0]
            return None

        # 1) Fast path by exact identification with and without leading zeros.
        provider = await find_by_identification(nit)
        if provider:
            return provider

        if normalized_nit != _normalize_nit(nit):
            provider = await find_by_identification(normalized_nit)
            if provider:
                return provider

        # 2) Fallback: list providers and compare normalized identification.
        fallback_res = await client.get(
            f"{self.base_url}/contacts",
            params={"type": "provider"},
            headers=self.headers,
        )
        if fallback_res.status_code == 200:
            contacts = _extract_contacts(fallback_res.json())
            for contact in contacts:
                candidate = _normalize_nit(str(contact.get("identification") or ""))
                if candidate and candidate == normalized_nit:
                    return contact

        # 3) If it does not exist, try creating provider.
        payload = {
            "name": nombre,
            "identification": nit,
            "type": ["provider"]
        }
        create_res = await client.post(f"{self.base_url}/contacts", json=payload, headers=self.headers)
        if create_res.status_code in [201, 200]:
            created = create_res.json()
            if isinstance(created, dict):
                return created.get("data", created)

        # 4) If creation failed because it already exists (or equivalent), retry lookup.
        create_error_text = create_res.text or ""
        if _is_duplicate_bill_error(create_error_text) or "exists" in create_error_text.lower() or "ya existe" in create_error_text.lower():
            provider = await find_by_identification(nit)
            if not provider and normalized_nit:
                provider = await find_by_identification(normalized_nit)
            if provider:
                return provider

        raise Exception(
            f"No se pudo encontrar ni crear el proveedor con NIT {nit} en Alegra. Detalle: {create_error_text}"
        )

    async def get_provider_id(self, client: httpx.AsyncClient, nit: str, nombre: str):
        provider = await self.resolve_provider_contact(client, nit, nombre)
        provider_id = provider.get("id") if isinstance(provider, dict) else None
        if provider_id is None:
            raise Exception(f"No se pudo resolver id de proveedor en Alegra para NIT {nit}.")
        return provider_id

    async def crear_bill(self, factura: FacturaDIAN):
        if not factura.nit_proveedor:
            raise Exception("No se puede causar en Alegra: El NIT del proveedor está vacío.")
        if not factura.items or len(factura.items) == 0:
            raise Exception("No se puede causar en Alegra: La factura no tiene items.")
        if not factura.total or factura.total <= 0:
            raise Exception("No se puede causar en Alegra: El total de la factura es inválido o cero.")

        async with httpx.AsyncClient() as client:
            # Primero buscamos el ID interno del proveedor en Alegra
            provider_id = await self.get_provider_id(client, factura.nit_proveedor, factura.nombre_proveedor)
            
            payload = {
                "date": factura.fecha_emision.strftime("%Y-%m-%d") if factura.fecha_emision else datetime.utcnow().strftime("%Y-%m-%d"),
                "dueDate": (factura.fecha_vencimiento or factura.fecha_emision or datetime.utcnow()).strftime("%Y-%m-%d"),
                "provider": {"id": provider_id},
                "items": [
                    {
                        "id": int(item.cuenta_contable_alegra) if item.cuenta_contable_alegra and str(item.cuenta_contable_alegra).isdigit() else int(settings.ALEGRA_CUENTA_DEFAULT_GASTOS),
                        "description": item.descripcion[:200],
                        "price": item.precio_unitario,
                        "quantity": item.cantidad,
                        "tax": [{"id": 1}], # Default IVA
                        "costCenter": {"id": int(item.centro_costo_alegra)} if item.centro_costo_alegra and str(item.centro_costo_alegra).isdigit() else None,
                    } for item in factura.items
                ],
                "type": "bill"
            }

            res = await client.post(f"{self.base_url}/bills", json=payload, headers=self.headers)
            if res.status_code in [200, 201]:
                return res.json()
            else:
                error_text = res.text
                if _is_duplicate_bill_error(error_text):
                    raise AlegraDuplicateBillError("La factura ya fue causada en Alegra (documento duplicado).")
                raise Exception(f"Error Alegra API al crear Bill: {error_text}")

alegra_service = AlegraService()
