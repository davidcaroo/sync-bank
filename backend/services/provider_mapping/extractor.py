from collections import Counter
import httpx

from services.alegra_service import alegra_service
from repositories.factura_repository import list_confirmed_provider_mappings
from repositories.db_utils import run_in_executor


class HistoricalExtractor:
    async def get_account_counts(self, nit_proveedor: str) -> tuple[Counter, int]:
        """One vote per successfully caused invoice whose items agree on a single
        (account, cost center) pair; mixed or unmapped invoices cast no vote."""
        rows = await run_in_executor(
            lambda: list_confirmed_provider_mappings(nit_proveedor)
        )
        counter = Counter()
        total = 0
        for row in rows:
            pairs = {
                (
                    str(item["cuenta"]),
                    str(item["centro_costo"]) if item.get("centro_costo") else None,
                )
                for item in row.get("mappings") or []
                if item.get("cuenta")
            }
            if len(pairs) == 1:
                counter[next(iter(pairs))] += 1
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
            provider = await alegra_service.find_provider_contact_by_nit(
                client, nit_proveedor
            )
            provider_id = (
                str(provider.get("id"))
                if isinstance(provider, dict) and provider.get("id") is not None
                else None
            )
            if not provider_id:
                return counter, total

            bills_seen = 0
            for page in range(max_pages):
                params = {
                    "start": page * page_size,
                    "limit": page_size,
                    "provider": provider_id,
                }
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
                    accounts = {
                        str(row["id"]) for row in categories if row.get("id")
                    }
                    if len(accounts) == 1:
                        cost_center = (bill.get("costCenter") or {}).get("id")
                        counter[
                            (
                                next(iter(accounts)),
                                str(cost_center) if cost_center else None,
                            )
                        ] += 1
                        total += 1
                    bills_seen += 1
                    if bills_seen >= max_bills:
                        return counter, total

                if len(bills) < page_size:
                    break

        return counter, total
