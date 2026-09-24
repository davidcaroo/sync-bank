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
    def __init__(self):
        self.saved = []

    async def save_mapping(self, **kwargs):
        self.saved.append(kwargs)
        return {"ok": True}


@pytest.mark.asyncio
async def test_provider_mapping_uses_historical_first():
    service = ProviderMappingService()
    service._historical = DummyExtractor(Counter({("5001", None): 5}), 5)
    service._alegra = DummyExtractor(Counter({("7001", None): 10}), 10)
    service._persistor = DummyPersistor()

    result = await service.compute_and_save_mapping("123")
    assert result is not None
    assert result["cuenta"] == "5001"
    assert result["source"] == "historical"


@pytest.mark.asyncio
async def test_provider_mapping_learns_account_and_cost_center_together():
    service = ProviderMappingService()
    service._historical = DummyExtractor(
        Counter({("5105", "12"): 3, ("5105", "15"): 1}),
        4,
    )
    service._persistor = DummyPersistor()

    result = await service.compute_and_save_mapping("900123456")

    assert result["cuenta"] == "5105"
    assert result["centro_costo"] == "12"
    assert result["confidence"] == 0.75
    assert service._persistor.saved[0]["centro_costo"] == "12"


@pytest.mark.asyncio
async def test_history_suggestion_returns_cost_center():
    service = ProviderMappingService()
    service._historical = DummyExtractor(Counter({("5105", "12"): 2}), 2)

    suggestion = await service.suggest_mapping_from_history("900123456")

    assert suggestion["cuenta"] == "5105"
    assert suggestion["centro_costo"] == "12"


@pytest.mark.asyncio
async def test_history_suggestion_works_with_one_prior_causation():
    service = ProviderMappingService()
    service._historical = DummyExtractor(Counter({("5105", "12"): 1}), 1)

    suggestion = await service.suggest_mapping_from_history("900123456")

    assert suggestion["cuenta"] == "5105"
    assert suggestion["centro_costo"] == "12"
