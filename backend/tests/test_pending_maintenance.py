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


def test_scheduled_sweep_only_covers_the_last_60_days():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    rows = [
        {"id": "new", "fecha_emision": now - timedelta(days=5)},
        {"id": "edge", "fecha_emision": (now - timedelta(days=59)).isoformat()},
        {"id": "old", "fecha_emision": now - timedelta(days=61)},
        {"id": "naive-old", "fecha_emision": (now - timedelta(days=90)).replace(tzinfo=None)},
        {"id": "no-date", "fecha_emision": None},
    ]

    kept = [r["id"] for r in pending_maintenance._recent(rows)]

    assert kept == ["new", "edge", "no-date"]


@pytest.mark.asyncio
async def test_stored_invoice_numbers_are_repaired_from_their_xml(monkeypatch):
    from tests.test_xml_parser import DECOY_INVOICE

    updates = []

    class Repo:
        async def get_facturas_paginated(self, *, page, page_size, **kwargs):
            rows = [
                {"id": 1, "numero_factura": "900320612", "xml_raw": DECOY_INVOICE},
                {"id": 2, "numero_factura": "T0916011103", "xml_raw": DECOY_INVOICE},
                {"id": 3, "numero_factura": "X", "xml_raw": None},
                {"id": 4, "numero_factura": "Y", "xml_raw": "<not-xml"},
            ]
            return type("R", (), {"data": rows if page == 1 else []})()

        async def update_factura_fields(self, factura_id, payload):
            updates.append((factura_id, payload))

    monkeypatch.setitem(pending_maintenance.state, "renumeradas", 0)

    await pending_maintenance._renumber(Repo())

    assert updates == [("1", {"numero_factura": "T0916011103"})]
    assert pending_maintenance.state["renumeradas"] == 1
