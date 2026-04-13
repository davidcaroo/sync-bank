from collections import Counter
import httpx

from services.alegra_service import alegra_service
from repositories.factura_repository import list_factura_items_by_nit
from repositories.db_utils import run_in_executor


class HistoricalExtractor:
    async def get_account_counts(self, nit_proveedor: str) -> tuple[Counter, int]:
        rows = await run_in_executor(lambda: list_factura_items_by_nit(nit_proveedor))
        counter = Counter()
        total = 0
        for row in rows:
            items = row.get("items_factura") or []
            for item in items:
                cuenta = item.get("cuenta_contable_alegra")
                if cuenta:
                    counter[str(cuenta)] += 1
                    total += 1
        return counter, total


class AlegraExtractor:
    async def get_account_counts(
        self,
        nit_proveedor: str,
        *,
        max_pages: int = 10,
        page_size: int = 30,
        max_bills: int = 300,
    ) -> tuple[Counter, int]:
        counter = Counter()
        total = 0
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            provider = await alegra_service.find_provider_contact_by_nit(client, nit_proveedor)
            provider_id = str(provider.get("id")) if isinstance(provider, dict) and provider.get("id") is not None else None
            if not provider_id:
                return counter, total

            bills_seen = 0
            for page in range(max_pages):
                params = {"start": page * page_size, "limit": page_size, "provider": provider_id}
                res = await client.get(
                    f"{alegra_service.base_url}/bills",
                    params=params,
                    headers=alegra_service.headers,
                )
                if res.status_code != 200:
                    break

                data = res.json()
                bills = data.get("data") or data
                if not isinstance(bills, list) or not bills:
                    break

                for bill in bills:
                    purchases = bill.get("purchases") or {}
                    categories = purchases.get("categories") or []
                    for row in categories:
                        cuenta = row.get("id")
                        if cuenta:
                            counter[str(cuenta)] += 1
                            total += 1
                    bills_seen += 1
                    if bills_seen >= max_bills:
                        return counter, total

                if len(bills) < page_size:
                    break

        return counter, total
