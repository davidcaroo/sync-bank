import base64
import re
from typing import Callable

import httpx

from config import settings
from models.factura import FacturaDIAN
from services.errors import AlegraDuplicateBillError, RemoteAPIError
from services.provider_tax_policy import resolve_provider_tax_mode
from services.timezone_service import now_bogota


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


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    raw = str(value).strip().replace(",", ".")
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _extract_contact_id_from_error_payload(payload) -> str | None:
    if isinstance(payload, dict):
        for key in ("contactId", "contact_id", "id"):
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _extract_contacts(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload.get("data")
        if isinstance(payload.get("results"), list):
            return payload.get("results")
    return []


def _extract_list_payload(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload.get("data")
        if isinstance(payload.get("data"), dict):
            data = payload.get("data")
            if isinstance(data.get("items"), list):
                return data.get("items")
            if isinstance(data.get("results"), list):
                return data.get("results")
        if isinstance(payload.get("results"), list):
            return payload.get("results")
        if isinstance(payload.get("items"), list):
            return payload.get("items")
    return []


def _normalize_invoice_ref(value: str | None) -> str:
    return re.sub(r"\W", "", str(value or "")).lower()


def _extract_numeric_id(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    match = re.match(r"\s*(\d+)", raw)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _is_service_description(text: str | None) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    hints = [
        "servicio",
        "instal",
        "mantenimiento",
        "soporte",
        "asesoria",
        "consultoria",
        "mano de obra",
        "honorario",
        "tecnico",
        "reparacion",
    ]
    return any(h in normalized for h in hints)


def _extract_bill_number(bill: dict) -> str:
    if not isinstance(bill, dict):
        return ""
    number_template = bill.get("numberTemplate")
    if isinstance(number_template, dict):
        candidate = str(number_template.get("number") or "").strip()
        if candidate:
            return candidate
    return str(bill.get("number") or "").strip()


def _extract_bill_items_accounting(bill: dict) -> list[dict]:
    if not isinstance(bill, dict):
        return []

    purchases = bill.get("purchases")
    if not isinstance(purchases, dict):
        return []

    categories = purchases.get("categories")
    if not isinstance(categories, list):
        return []

    result = []
    for row in categories:
        if not isinstance(row, dict):
            continue

        cuenta = row.get("id")
        cuenta_value = str(cuenta) if cuenta is not None else None

        cost_center = row.get("costCenter")
        centro = None
        if isinstance(cost_center, dict):
            centro_id = cost_center.get("id")
            centro = str(centro_id) if centro_id is not None else None

        descripcion = (
            str(row.get("description") or "").strip()
            or str(row.get("name") or "").strip()
            or None
        )

        result.append(
            {
                "descripcion": descripcion,
                "cuenta_contable_alegra": cuenta_value,
                "centro_costo_alegra": centro,
            }
        )

    return result


def _build_bill_observations(factura: FacturaDIAN, max_length: int = 500) -> str:
    concepts: list[str] = []
    seen: set[str] = set()

    for item in factura.items or []:
        raw_desc = (item.descripcion or "").strip()
        if not raw_desc:
            continue
        normalized_desc = re.sub(r"\s+", " ", raw_desc)
        key = normalized_desc.lower()
        if key in seen:
            continue
        seen.add(key)
        concepts.append(normalized_desc)

    if concepts:
        concept_text = "; ".join(concepts)
    else:
        concept_text = "Sin detalle de items"

    footer = f"Factura DIAN {factura.numero_factura or ''} | CUFE {factura.cufe or 'N/A'}"
    text = f"Concepto: {concept_text}. {footer}".strip()
    if len(text) <= max_length:
        return text

    reserved = len(footer) + len("Concepto: . ")
    available_for_concepts = max(20, max_length - reserved)
    clipped_concepts = concept_text[: available_for_concepts - 3].rstrip() + "..."
    return f"Concepto: {clipped_concepts}. {footer}"[:max_length]


class AlegraClient:
    def __init__(self, http_client_factory: Callable[[], httpx.AsyncClient] | None = None):
        auth_str = f"{settings.ALEGRA_EMAIL}:{settings.ALEGRA_TOKEN}"
        self.auth_header = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json",
        }
        self.base_url = "https://api.alegra.com/api/v1"
        self._categories = None
        self._cost_centers = None
        self._taxes = None
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        )

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
                result.append(
                    {
                        "id": category_id,
                        "name": name,
                        "code": code,
                        "type": node.get("type"),
                    }
                )

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
        if res.status_code != 200:
            raise RemoteAPIError(f"Error Alegra API al listar categorias: {res.text}")
        data = res.json()
        raw_categories = data.get("data", data) if isinstance(data, dict) else data
        self._categories = self._flatten_categories(raw_categories)
        return self._categories

    async def get_cost_centers(self, client: httpx.AsyncClient):
        if self._cost_centers:
            return self._cost_centers
        res = await client.get(f"{self.base_url}/cost-centers", headers=self.headers)
        if res.status_code != 200:
            raise RemoteAPIError(f"Error Alegra API al listar centros de costo: {res.text}")
        data = res.json()
        self._cost_centers = data.get("data", data) if isinstance(data, dict) else data
        return self._cost_centers

    async def get_taxes(self, client: httpx.AsyncClient):
        if self._taxes is not None:
            return self._taxes

        res = await client.get(f"{self.base_url}/taxes", headers=self.headers)
        if res.status_code != 200:
            raise RemoteAPIError(f"Error Alegra API al listar impuestos: {res.text}")

        data = res.json()
        raw_taxes = _extract_list_payload(data)
        if not raw_taxes and isinstance(data, list):
            raw_taxes = data

        taxes = []
        for row in raw_taxes or []:
            if not isinstance(row, dict):
                continue

            status = str(row.get("status") or "").strip().lower()
            if status in {"inactive", "disabled"}:
                continue

            tax_id = row.get("id")
            if tax_id is None:
                continue

            taxes.append(
                {
                    "id": tax_id,
                    "name": row.get("name"),
                    "type": str(row.get("type") or "").strip().upper(),
                    "percentage": _to_float(row.get("percentage") or row.get("rate"), 0.0),
                }
            )

        self._taxes = taxes
        return self._taxes

    def _resolve_tax_id_for_percentage(
        self,
        taxes: list[dict],
        percentage: float,
        *,
        item_description: str | None = None,
        provider_tax_mode: str = "auto",
    ) -> int | None:
        target = _to_float(percentage, 0.0)
        if target <= 0:
            return None

        candidates = []
        for tax in taxes or []:
            current = _to_float(tax.get("percentage"), 0.0)
            if abs(current - target) <= 0.01:
                candidates.append(tax)

        if not candidates:
            return None

        # Business rule: avoid "IVA generado" for purchases caused from DIAN invoices.
        # Prefer deductible IVA (compras/servicios) by item context.
        mode = (provider_tax_mode or "auto").strip().lower()
        if mode == "servicios":
            prefers_services = True
        elif mode == "compras":
            prefers_services = False
        else:
            prefers_services = _is_service_description(item_description)

        def rank(tax: dict):
            tax_type = str(tax.get("type") or "").upper()
            name = str(tax.get("name") or "").strip().lower()
            pct = _to_float(tax.get("percentage"), 0.0)

            is_iva = tax_type == "IVA"
            is_generated = "generado" in name
            is_desc = "desc" in name or "descont" in name
            is_services = "servicio" in name
            is_purchases = "compra" in name

            # lower score => better candidate
            score = 0
            score += 0 if is_iva else 100
            score += 200 if is_generated else 0
            score += 0 if is_desc else 50

            if prefers_services:
                score += 0 if is_services else 15
            else:
                score += 0 if is_purchases else 15

            score += int(abs(pct - target) * 100)
            return score

        candidates.sort(
            key=rank
        )

        chosen = candidates[0].get("id")
        if chosen is None:
            return None
        try:
            return int(chosen)
        except Exception:
            return None

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
            raise RemoteAPIError(f"Error Alegra API al listar contactos: {res.text}")
        return _extract_contacts(res.json())

    async def get_contact(self, client: httpx.AsyncClient, contact_id: str):
        res = await client.get(f"{self.base_url}/contacts/{contact_id}", headers=self.headers)
        if res.status_code != 200:
            raise RemoteAPIError(f"Error Alegra API al consultar contacto {contact_id}: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def create_contact(self, client: httpx.AsyncClient, payload: dict):
        res = await client.post(f"{self.base_url}/contacts", json=payload, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise RemoteAPIError(f"Error Alegra API al crear contacto: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def update_contact(self, client: httpx.AsyncClient, contact_id: str, payload: dict):
        res = await client.put(f"{self.base_url}/contacts/{contact_id}", json=payload, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise RemoteAPIError(f"Error Alegra API al actualizar contacto {contact_id}: {res.text}")
        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def delete_contact(self, client: httpx.AsyncClient, contact_id: str):
        res = await client.delete(f"{self.base_url}/contacts/{contact_id}", headers=self.headers)
        if res.status_code not in [200, 202, 204]:
            raise RemoteAPIError(f"Error Alegra API al eliminar contacto {contact_id}: {res.text}")
        return True

    async def resolve_provider_contact(self, client: httpx.AsyncClient, nit: str, nombre: str) -> dict:
        normalized_nit = _normalize_nit(nit)

        async def find_by_identification(value: str | None, *, contact_type: str | None = "provider"):
            if not value:
                return None
            params = {"identification": value}
            if contact_type:
                params["type"] = contact_type
            res = await client.get(
                f"{self.base_url}/contacts",
                params=params,
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

        provider = await find_by_identification(nit, contact_type="provider")
        if provider:
            return provider

        if normalized_nit != _normalize_nit(nit):
            provider = await find_by_identification(normalized_nit, contact_type="provider")
            if provider:
                return provider

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

        payload = {
            "name": nombre,
            "identification": nit,
            "type": ["provider"],
        }
        create_res = await client.post(f"{self.base_url}/contacts", json=payload, headers=self.headers)
        if create_res.status_code in [201, 200]:
            created = create_res.json()
            if isinstance(created, dict):
                return created.get("data", created)

        create_error_payload = None
        try:
            create_error_payload = create_res.json()
        except Exception:
            create_error_payload = None

        create_error_text = create_res.text or ""
        lower_error = create_error_text.lower()
        duplicate_contact = (
            _is_duplicate_bill_error(create_error_text)
            or "exists" in lower_error
            or "ya existe" in lower_error
            or (isinstance(create_error_payload, dict) and str(create_error_payload.get("code") or "") == "2006")
        )

        if duplicate_contact:
            provider = await find_by_identification(nit, contact_type="provider")
            if not provider and normalized_nit:
                provider = await find_by_identification(normalized_nit, contact_type="provider")
            if not provider:
                provider = await find_by_identification(nit, contact_type=None)
            if not provider and normalized_nit:
                provider = await find_by_identification(normalized_nit, contact_type=None)
            if not provider:
                contact_id = _extract_contact_id_from_error_payload(create_error_payload)
                if contact_id:
                    try:
                        provider = await self.get_contact(client, contact_id)
                    except Exception:
                        provider = None
            if provider:
                return provider

        raise RemoteAPIError(
            f"No se pudo encontrar ni crear el proveedor con NIT {nit} en Alegra. Detalle: {create_error_text}"
        )

    async def find_provider_contact_by_nit(self, client: httpx.AsyncClient, nit: str) -> dict | None:
        normalized_nit = _normalize_nit(nit)
        if not normalized_nit:
            return None

        res = await client.get(
            f"{self.base_url}/contacts",
            params={"identification": nit, "type": "provider"},
            headers=self.headers,
        )
        if res.status_code != 200:
            return None

        contacts = _extract_contacts(res.json())
        for contact in contacts:
            candidate = _normalize_nit(str(contact.get("identification") or ""))
            if candidate == normalized_nit:
                return contact
        return contacts[0] if contacts else None

    async def _find_bill_by_number(
        self,
        client: httpx.AsyncClient,
        *,
        numero_factura: str,
        provider_id: str | None,
        max_pages: int = 20,
    ) -> dict | None:
        target = _normalize_invoice_ref(numero_factura)
        if not target:
            return None

        for page in range(max_pages):
            params = {
                "start": page * 30,
                "limit": 30,
            }
            if provider_id:
                params["provider"] = provider_id

            res = await client.get(f"{self.base_url}/bills", params=params, headers=self.headers)
            if res.status_code != 200:
                continue

            bills = _extract_list_payload(res.json())
            if not bills:
                break

            for bill in bills:
                number_raw = _extract_bill_number(bill)
                number = _normalize_invoice_ref(number_raw)
                if number == target or number.endswith(target) or target.endswith(number):
                    return bill

            if len(bills) < 30:
                break

        return None

    async def get_bill_by_id(self, client: httpx.AsyncClient, bill_id: str) -> dict | None:
        res = await client.get(f"{self.base_url}/bills/{bill_id}", headers=self.headers)
        if res.status_code == 404:
            return None
        if res.status_code != 200:
            raise RemoteAPIError(f"Error Alegra API al consultar bill {bill_id}: {res.text}")

        data = res.json()
        return data.get("data", data) if isinstance(data, dict) else data

    async def get_bill_accounting_by_invoice(
        self,
        *,
        nit_proveedor: str | None,
        numero_factura: str | None,
        max_pages: int = 20,
    ) -> dict | None:
        if not numero_factura:
            return None

        async with self._http_client_factory() as client:
            provider = await self.find_provider_contact_by_nit(client, nit_proveedor or "")
            provider_id = str(provider.get("id")) if isinstance(provider, dict) and provider.get("id") is not None else None

            bill = await self._find_bill_by_number(
                client,
                numero_factura=numero_factura,
                provider_id=provider_id,
                max_pages=max_pages,
            )

            if not bill:
                bill = await self._find_bill_by_number(
                    client,
                    numero_factura=numero_factura,
                    provider_id=None,
                    max_pages=max_pages,
                )

            if not bill:
                return None

            bill_id = bill.get("id")
            items = _extract_bill_items_accounting(bill)
            return {
                "bill_id": str(bill_id) if bill_id is not None else None,
                "items": items,
            }

    async def get_provider_id(self, client: httpx.AsyncClient, nit: str, nombre: str):
        provider = await self.resolve_provider_contact(client, nit, nombre)
        provider_id = provider.get("id") if isinstance(provider, dict) else None
        if provider_id is None:
            raise RemoteAPIError(f"No se pudo resolver id de proveedor en Alegra para NIT {nit}.")
        return provider_id

    async def crear_bill(self, factura: FacturaDIAN):
        if not factura.nit_proveedor:
            raise RemoteAPIError("No se puede causar en Alegra: El NIT del proveedor esta vacio.")
        if not factura.items or len(factura.items) == 0:
            raise RemoteAPIError("No se puede causar en Alegra: La factura no tiene items.")
        if not factura.total or factura.total <= 0:
            raise RemoteAPIError("No se puede causar en Alegra: El total de la factura es invalido o cero.")

        async with self._http_client_factory() as client:
            provider_id = await self.get_provider_id(client, factura.nit_proveedor, factura.nombre_proveedor)
            taxes = await self.get_taxes(client)
            now_local = now_bogota()
            provider_tax_mode = resolve_provider_tax_mode(factura.nit_proveedor, factura.nombre_proveedor)

            categories_payload = []
            cost_center_ids: list[int] = []
            for item in factura.items:
                categoria_id = _extract_numeric_id(item.cuenta_contable_alegra)
                if categoria_id is None:
                    categoria_id = _extract_numeric_id(settings.ALEGRA_CUENTA_DEFAULT_GASTOS)
                if categoria_id is None:
                    raise RemoteAPIError("No se pudo resolver la cuenta contable para la causacion en Alegra.")

                centro_costo_id = _extract_numeric_id(item.centro_costo_alegra)
                if centro_costo_id is not None:
                    cost_center_ids.append(centro_costo_id)

                categoria = {
                    "id": categoria_id,
                    "price": item.precio_unitario,
                    "quantity": item.cantidad,
                    "costCenter": {"id": centro_costo_id} if centro_costo_id is not None else None,
                }

                iva_porcentaje = _to_float(getattr(item, "iva_porcentaje", 0.0), 0.0)
                if iva_porcentaje > 0:
                    tax_id = self._resolve_tax_id_for_percentage(
                        taxes,
                        iva_porcentaje,
                        item_description=getattr(item, "descripcion", None),
                        provider_tax_mode=provider_tax_mode,
                    )
                    if tax_id is None:
                        raise RemoteAPIError(
                            f"No se encontro un impuesto activo en Alegra para IVA {iva_porcentaje:.2f}%. "
                            "Revisa la configuracion de impuestos en Alegra."
                        )
                    categoria["tax"] = [{"id": tax_id}]

                categories_payload.append(categoria)

            resolved_bill_cost_center = None
            if cost_center_ids:
                # Alegra bill UI uses a single top-level cost center for purchases.
                # If multiple values are present, keep a deterministic first one.
                resolved_bill_cost_center = cost_center_ids[0]

            payload = {
                "date": factura.fecha_emision.strftime("%Y-%m-%d") if factura.fecha_emision else now_local.strftime("%Y-%m-%d"),
                "dueDate": (factura.fecha_vencimiento or factura.fecha_emision or now_local).strftime("%Y-%m-%d"),
                "provider": {"id": provider_id},
                "costCenter": {"id": resolved_bill_cost_center} if resolved_bill_cost_center is not None else None,
                "numberTemplate": {
                    "number": factura.numero_factura,
                },
                "purchases": {
                    "categories": categories_payload
                },
                "observations": _build_bill_observations(factura),
            }

            res = await client.post(f"{self.base_url}/bills", json=payload, headers=self.headers)
            if res.status_code in [200, 201]:
                return res.json()

            error_text = res.text
            if _is_duplicate_bill_error(error_text):
                raise AlegraDuplicateBillError("La factura ya fue causada en Alegra (documento duplicado).")
            raise RemoteAPIError(f"Error Alegra API al crear Bill: {error_text}")
