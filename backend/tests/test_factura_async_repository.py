import pytest

from repositories.factura_async_repository import (
    SyncCausacionRepositoryAdapter,
    SyncFacturaRepositoryAdapter,
)


@pytest.mark.asyncio
async def test_sync_factura_async_repository_adapter_get_stats(monkeypatch):
    async def fake_run_in_executor(action):
        return action()

    monkeypatch.setattr(
        "repositories.factura_async_repository.get_facturas_stats",
        lambda: [{"estado": "pendiente"}],
    )

    adapter = SyncFacturaRepositoryAdapter(run_in_executor=fake_run_in_executor)

    rows = await adapter.get_facturas_stats()

    assert rows == [{"estado": "pendiente"}]


@pytest.mark.asyncio
async def test_sync_causacion_repository_adapter_calls_save(monkeypatch):
    observed = {}

    async def fake_run_in_executor(action):
        return action()

    def fake_save_causacion(payload):
        observed["payload"] = payload

    monkeypatch.setattr("repositories.factura_async_repository.save_causacion", fake_save_causacion)

    adapter = SyncCausacionRepositoryAdapter(run_in_executor=fake_run_in_executor)

    payload = {"factura_id": "f-1", "estado": "exitoso"}
    await adapter.save_causacion(payload)

    assert observed["payload"]["factura_id"] == "f-1"
    assert observed["payload"]["estado"] == "exitoso"
