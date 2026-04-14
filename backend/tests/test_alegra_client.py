from models.factura import FacturaDIAN, FacturaItem
from services.alegra_client import AlegraClient, _build_bill_observations
from services.provider_tax_policy import resolve_provider_tax_mode
import pytest


def test_flatten_categories_filters_inactive_and_dedups():
    client = AlegraClient()
    payload = [
        {
            "id": 10,
            "name": "Gastos Operativos",
            "status": "active",
            "children": [
                {"id": 11, "name": "Papeleria", "status": "inactive"},
                {"id": 12, "name": "Transporte", "status": "active"},
            ],
        },
        {"id": 10, "name": "Gastos Operativos DUP", "status": "active"},
    ]

    flattened = client._flatten_categories(payload)
    by_id = {str(item["id"]): item for item in flattened}

    assert "11" not in by_id
    assert "10" in by_id
    assert "12" in by_id


def test_build_bill_observations_truncates_and_includes_footer():
    factura = FacturaDIAN(
        cufe="CUFE-123",
        numero_factura="FAC-9",
        fecha_emision=None,
        nit_proveedor="9001",
        nombre_proveedor="Proveedor",
        nit_receptor="8001",
        subtotal=1000,
        iva=190,
        total=1190,
        items=[
            FacturaItem(
                descripcion="Servicio de mantenimiento preventivo mensual para la sede principal",
                cantidad=1,
                precio_unitario=1000,
                descuento=0,
                iva_porcentaje=19,
                total_linea=1000,
            )
        ],
    )

    text = _build_bill_observations(factura, max_length=80)

    assert "Factura DIAN FAC-9" in text
    assert "CUFE CUFE-123" in text
    assert len(text) <= 80


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class _FakeClient:
    def __init__(self):
        self._contacts_by_identification = {
            ("92601258", "provider"): [],
            ("92601258", None): [
                {
                    "id": "641",
                    "name": "FERRETERIA DONDE ROBERT C.J - ROBER SEGUNDO MARTINEZ MENDIVIL",
                    "identification": "92601258",
                    "type": ["client"],
                }
            ],
        }

    async def get(self, url, params=None, headers=None):
        if url.endswith("/contacts"):
            identification = (params or {}).get("identification")
            contact_type = (params or {}).get("type")
            contacts = self._contacts_by_identification.get((identification, contact_type), [])
            return _FakeResponse(200, payload=contacts, text=str(contacts))

        if "/contacts/" in url:
            return _FakeResponse(
                200,
                payload={
                    "id": "641",
                    "name": "FERRETERIA DONDE ROBERT C.J - ROBER SEGUNDO MARTINEZ MENDIVIL",
                    "identification": "92601258",
                    "type": ["client"],
                },
            )

        return _FakeResponse(404, payload={"message": "not found"}, text="not found")

    async def post(self, url, json=None, headers=None):
        if url.endswith("/contacts"):
            payload = {
                "message": "Ya existe un contacto con la identificacion 92601258",
                "code": 2006,
                "contactId": "641",
            }
            return _FakeResponse(400, payload=payload, text=str(payload))
        return _FakeResponse(404, payload={"message": "not found"}, text="not found")


@pytest.mark.asyncio
async def test_resolve_provider_contact_uses_existing_contact_when_duplicate_create():
    client = AlegraClient()
    fake_http = _FakeClient()

    provider = await client.resolve_provider_contact(fake_http, "92601258", "Proveedor Demo")

    assert provider is not None
    assert str(provider.get("id")) == "641"


def test_resolve_tax_id_for_percentage_prefers_exact_iva_match():
    client = AlegraClient()
    taxes = [
        {"id": 1, "type": "IVA", "percentage": 0.0},
        {"id": 4, "type": "IVA", "percentage": 19.0, "name": "Iva Generado 19%"},
        {"id": 5, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por compras"},
        {"id": 6, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por servicios"},
        {"id": 9, "type": "OTHER", "percentage": 19.0, "name": "otro"},
    ]

    tax_id = client._resolve_tax_id_for_percentage(taxes, 19.0)

    assert tax_id == 5


def test_resolve_tax_id_for_percentage_prefers_services_when_description_matches():
    client = AlegraClient()
    taxes = [
        {"id": 4, "type": "IVA", "percentage": 19.0, "name": "Iva Generado 19%"},
        {"id": 5, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por compras"},
        {"id": 6, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por servicios"},
    ]

    tax_id = client._resolve_tax_id_for_percentage(
        taxes,
        19.0,
        item_description="Servicio de instalacion de camaras",
    )

    assert tax_id == 6


def test_resolve_tax_id_for_percentage_forced_compras_mode_overrides_description():
    client = AlegraClient()
    taxes = [
        {"id": 5, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por compras"},
        {"id": 6, "type": "IVA", "percentage": 19.0, "name": "IVA desc 19% por servicios"},
    ]

    tax_id = client._resolve_tax_id_for_percentage(
        taxes,
        19.0,
        item_description="Servicio de instalacion",
        provider_tax_mode="compras",
    )

    assert tax_id == 5


def test_resolve_provider_tax_mode_defaults_supermarket_to_compras():
    mode = resolve_provider_tax_mode(None, "SUPERMERCADOS D1 S.A.S")

    assert mode == "compras"


def test_resolve_tax_id_for_percentage_returns_none_when_no_match():
    client = AlegraClient()
    taxes = [{"id": 1, "type": "IVA", "percentage": 0.0}]

    tax_id = client._resolve_tax_id_for_percentage(taxes, 19.0)

    assert tax_id is None