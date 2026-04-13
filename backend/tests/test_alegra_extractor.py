import pytest

from services.provider_mapping.extractor import AlegraExtractor


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, *args, **kwargs):
        self._calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        self._calls += 1
        payload = {
            "data": [
                {
                    "purchases": {
                        "categories": [{"id": "6001"}, {"id": "6001"}, {"id": "7001"}]
                    }
                }
            ]
        }
        return FakeResponse(200, payload)


@pytest.mark.asyncio
async def test_alegra_extractor_counts_accounts(monkeypatch):
    monkeypatch.setattr("services.provider_mapping.extractor.httpx.AsyncClient", FakeClient)

    async def fake_find_provider(*args, **kwargs):
        return {"id": "123"}

    monkeypatch.setattr("services.provider_mapping.extractor.alegra_service.find_provider_contact_by_nit", fake_find_provider)

    extractor = AlegraExtractor()
    counter, total = await extractor.get_account_counts("9001", max_pages=1, page_size=30, max_bills=10)

    assert total == 3
    assert counter["6001"] == 2
    assert counter["7001"] == 1
