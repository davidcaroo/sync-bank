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
                    "costCenter": {"id": 12},
                    "purchases": {"categories": [{"id": "6001"}, {"id": "6001"}]},
                },
                {
                    "costCenter": {"id": 12},
                    "purchases": {"categories": [{"id": "6001"}, {"id": "7001"}]},
                },
                {"purchases": {"categories": [{"id": "6001"}]}},
            ]
        }
        return FakeResponse(200, payload)


@pytest.mark.asyncio
async def test_alegra_extractor_votes_one_pair_per_bill(monkeypatch):
    monkeypatch.setattr(
        "services.provider_mapping.extractor.httpx.AsyncClient", FakeClient
    )

    async def fake_find_provider(*args, **kwargs):
        return {"id": "123"}

    monkeypatch.setattr(
        "services.provider_mapping.extractor.alegra_service.find_provider_contact_by_nit",
        fake_find_provider,
    )

    extractor = AlegraExtractor()
    counter, total = await extractor.get_account_counts(
        "9001", max_pages=1, page_size=30, max_bills=10
    )

    # The mixed-account bill casts no vote; the others vote once each.
    assert total == 2
    assert counter[("6001", "12")] == 1
    assert counter[("6001", None)] == 1


@pytest.mark.asyncio
async def test_alegra_extractor_filters_by_client_id_and_accepts_a_bare_list(monkeypatch):
    seen = {}

    class ListClient(FakeClient):
        async def get(self, url, params=None, **kwargs):
            seen.update(params)
            return FakeResponse(
                200,
                [{"costCenter": {"id": 7}, "purchases": {"categories": [{"id": "5290"}]}}],
            )

    monkeypatch.setattr(
        "services.provider_mapping.extractor.httpx.AsyncClient", ListClient
    )

    async def fake_find_provider(*args, **kwargs):
        return {"id": "641"}

    monkeypatch.setattr(
        "services.provider_mapping.extractor.alegra_service.find_provider_contact_by_nit",
        fake_find_provider,
    )

    counter, total = await AlegraExtractor().get_account_counts("9001", max_pages=1)

    assert seen["client_id"] == "641" and "provider" not in seen
    assert total == 1 and counter[("5290", "7")] == 1


@pytest.mark.asyncio
async def test_alegra_extractor_only_learns_from_the_learning_year(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "LEARNING_START_DATE", "2026-01-01")
    seen = {}

    class DatedClient(FakeClient):
        async def get(self, url, params=None, **kwargs):
            seen.update(params)
            bill = lambda d, acc: {  # noqa: E731
                "date": d,
                "costCenter": {"id": 7},
                "purchases": {"categories": [{"id": acc}]},
            }
            return FakeResponse(200, [bill("2026-03-01", "5290"), bill("2025-12-30", "9999")])

    monkeypatch.setattr(
        "services.provider_mapping.extractor.httpx.AsyncClient", DatedClient
    )

    async def fake_find_provider(*args, **kwargs):
        return {"id": "641"}

    monkeypatch.setattr(
        "services.provider_mapping.extractor.alegra_service.find_provider_contact_by_nit",
        fake_find_provider,
    )

    counter, total = await AlegraExtractor().get_account_counts("9001", page_size=2)

    assert seen["order_field"] == "date" and seen["order_direction"] == "DESC"
    assert total == 1 and list(counter) == [("5290", "7")]
