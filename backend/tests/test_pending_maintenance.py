import pytest

from services import pending_maintenance


class _Provider:
    def __init__(self):
        self.computed = []

    async def compute_and_save_mapping(self, nit, nombre):
        self.computed.append(nit)

    async def suggest_mapping_from_history(self, *args, **kwargs):
        return None


def _patch(monkeypatch, provider):
    monkeypatch.setattr(
        pending_maintenance,
        "get_config_cuenta",
        lambda nit: {"id_cuenta_alegra": "5290", "id_centro_costo_alegra": "7", "source": "alegra"},
    )
    monkeypatch.setattr(pending_maintenance, "provider_mapping_service", provider)


@pytest.mark.asyncio
async def test_scheduled_run_keeps_existing_rules_without_asking_alegra(monkeypatch):
    provider = _Provider()
    _patch(monkeypatch, provider)

    rule = await pending_maintenance._rule_for("900", "P", {}, relearn=False)

    assert rule["cuenta"] == "5290" and provider.computed == []


@pytest.mark.asyncio
async def test_manual_sweep_relearns_non_manual_rules(monkeypatch):
    provider = _Provider()
    _patch(monkeypatch, provider)

    await pending_maintenance._rule_for("900", "P", {}, relearn=True)

    assert provider.computed == ["900"]


@pytest.mark.asyncio
async def test_scheduled_run_does_nothing_while_a_sweep_is_running(monkeypatch):
    monkeypatch.setitem(pending_maintenance.state, "running", True)

    async def boom(relearn):
        raise AssertionError("must not start a second sweep")

    monkeypatch.setattr(pending_maintenance, "_run", boom)

    await pending_maintenance.run_scheduled()
