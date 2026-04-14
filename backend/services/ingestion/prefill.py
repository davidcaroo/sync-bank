import httpx

from services.alegra_service import alegra_service


class IngestionPrefill:
    async def build_prefill_context(self, *, apply_ai: bool) -> dict:
        if not apply_ai:
            return {"categories": [], "cost_centers": []}

        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            categories = await alegra_service.get_categories(client)
            cost_centers = await alegra_service.get_cost_centers(client)

        return {
            "categories": categories or [],
            "cost_centers": cost_centers or [],
        }