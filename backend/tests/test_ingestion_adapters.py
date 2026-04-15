import pytest

from repositories.ingestion_adapters import (
    SyncFacturaRepositoryAdapter,
    SyncProviderConfigRepositoryAdapter,
)


@pytest.mark.asyncio
async def test_sync_factura_repository_adapter_delegates_calls():
    calls = {}

    async def fake_run_in_executor(action):
        return action()

    def fake_find_factura_by_cufe(cufe):
        calls["find_cufe"] = cufe
        return {"id": "f1", "cufe": cufe}

    def fake_save_factura(payload, items):
        calls["save_payload"] = payload
        calls["save_items"] = items
        return {"factura_id": "f1", "duplicado": False}

    adapter = SyncFacturaRepositoryAdapter(
        run_in_executor=fake_run_in_executor,
        find_factura_by_cufe=fake_find_factura_by_cufe,
        save_factura=fake_save_factura,
    )

    found = await adapter.find_by_cufe("CUFE-1")
    saved = await adapter.save_factura({"cufe": "CUFE-1"}, [{"descripcion": "x"}])

    assert found["id"] == "f1"
    assert saved["factura_id"] == "f1"
    assert calls["find_cufe"] == "CUFE-1"
    assert calls["save_payload"]["cufe"] == "CUFE-1"
    assert calls["save_items"][0]["descripcion"] == "x"


@pytest.mark.asyncio
async def test_sync_provider_config_repository_adapter_delegates_calls():
    calls = {}

    async def fake_run_in_executor(action):
        return action()

    def fake_get_config_cuenta(nit):
        calls["get_nit"] = nit
        return {"id_cuenta_alegra": "5001"}

    def fake_sync_proveedor_nombre(nit, nombre):
        calls["sync_nit"] = nit
        calls["sync_nombre"] = nombre

    adapter = SyncProviderConfigRepositoryAdapter(
        run_in_executor=fake_run_in_executor,
        get_config_cuenta=fake_get_config_cuenta,
        sync_config_proveedor_nombre=fake_sync_proveedor_nombre,
    )

    config = await adapter.get_config_cuenta("9001")
    await adapter.sync_proveedor_nombre("9001", "Proveedor")

    assert config["id_cuenta_alegra"] == "5001"
    assert calls["get_nit"] == "9001"
    assert calls["sync_nit"] == "9001"
    assert calls["sync_nombre"] == "Proveedor"
