import httpx
import base64
from datetime import datetime
from config import settings
from models.factura import FacturaDIAN

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

    async def get_provider_id(self, client: httpx.AsyncClient, nit: str, nombre: str):
        # 1. Buscar si el proveedor existe
        res = await client.get(f"{self.base_url}/contacts/?identification={nit}&type=provider", headers=self.headers)
        if res.status_code == 200:
            contacts = res.json()
            if isinstance(contacts, list) and len(contacts) > 0:
                return contacts[0]["id"]
        
        # 2. Si no existe o hubo un error leve al buscarlo, se intenta crear
        payload = {
            "name": nombre,
            "identification": nit,
            "type": ["provider"]
        }
        create_res = await client.post(f"{self.base_url}/contacts", json=payload, headers=self.headers)
        if create_res.status_code in [201, 200]:
            return create_res.json()["id"]
            
        raise Exception(f"No se pudo encontrar ni crear el proveedor con NIT {nit} en Alegra.")

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
                raise Exception(f"Error Alegra API al crear Bill: {res.text}")

alegra_service = AlegraService()
