class IngestionPrefill:
    async def build_prefill_context(self, *, apply_ai: bool) -> dict:
        return {"categories": [], "cost_centers": []}
