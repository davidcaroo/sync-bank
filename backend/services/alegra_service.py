from services.alegra_client import AlegraClient
from services.errors import AlegraDuplicateBillError


class AlegraService:
    """Thin facade for business modules that depend on Alegra integration."""

    def __init__(self):
        self._client = AlegraClient()

    @property
    def headers(self):
        return self._client.headers

    @property
    def base_url(self):
        return self._client.base_url

    async def get_categories(self, client):
        return await self._client.get_categories(client)

    async def get_cost_centers(self, client):
        return await self._client.get_cost_centers(client)

    async def list_contacts(self, client, contact_type: str | None = "provider", start: int = 0, limit: int = 30, identification: str | None = None):
        return await self._client.list_contacts(
            client,
            contact_type=contact_type,
            start=start,
            limit=limit,
            identification=identification,
        )

    async def get_contact(self, client, contact_id: str):
        return await self._client.get_contact(client, contact_id)

    async def create_contact(self, client, payload: dict):
        return await self._client.create_contact(client, payload)

    async def update_contact(self, client, contact_id: str, payload: dict):
        return await self._client.update_contact(client, contact_id, payload)

    async def delete_contact(self, client, contact_id: str):
        return await self._client.delete_contact(client, contact_id)

    async def resolve_provider_contact(self, client, nit: str, nombre: str) -> dict:
        return await self._client.resolve_provider_contact(client, nit, nombre)

    async def find_provider_contact_by_nit(self, client, nit: str) -> dict | None:
        return await self._client.find_provider_contact_by_nit(client, nit)

    async def get_bill_accounting_by_invoice(self, *, nit_proveedor: str | None, numero_factura: str | None, max_pages: int = 20) -> dict | None:
        return await self._client.get_bill_accounting_by_invoice(
            nit_proveedor=nit_proveedor,
            numero_factura=numero_factura,
            max_pages=max_pages,
        )

    async def get_bill_by_id(self, client, bill_id: str) -> dict | None:
        return await self._client.get_bill_by_id(client, bill_id)

    async def get_provider_id(self, client, nit: str, nombre: str):
        return await self._client.get_provider_id(client, nit, nombre)

    async def crear_bill(self, factura):
        return await self._client.crear_bill(factura)

alegra_service = AlegraService()
