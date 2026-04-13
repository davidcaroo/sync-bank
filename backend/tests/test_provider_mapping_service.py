import pytest
from collections import Counter

from services.provider_mapping_service import ProviderMappingService


class DummyExtractor:
    def __init__(self, counter, total):
        self._counter = counter
        self._total = total

    async def get_account_counts(self, nit_proveedor: str):
        return self._counter, self._total


class DummyPersistor:
    async def save_mapping(self, **kwargs):
        return {"ok": True}


@pytest.mark.asyncio
async def test_provider_mapping_uses_historical_first():
    service = ProviderMappingService()
    service._historical = DummyExtractor(Counter({"5001": 5}), 5)
    service._alegra = DummyExtractor(Counter({"7001": 10}), 10)
    service._persistor = DummyPersistor()

    result = await service.compute_and_save_mapping("123")
    assert result is not None
    assert result["cuenta"] == "5001"
    assert result["source"] == "historical"
