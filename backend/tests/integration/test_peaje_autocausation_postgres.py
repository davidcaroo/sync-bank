"""Acceptance: DEVISAB peaje XML through the real ingestion, DB and autocausation."""

import pytest

from config import settings
from peaje_fixture import PEAJE_ATTACHED_DOCUMENT_XML, PEAJE_DESCRIPTION
from repositories.config_repository import save_config_cuenta
from repositories.database import connection
from services.auto_causacion_service import auto_causacion_service
from services.errors import RemoteAPIError
from services.ingestion_service import XMLDocument, ingestion_service

NIT = "901209021"


@pytest.fixture(autouse=True)
def peaje_receiver_is_the_company(monkeypatch):
    monkeypatch.setattr(settings, "COMPANY_NIT", "800123000")


def _peaje_xml(n: int) -> str:
    return PEAJE_ATTACHED_DOCUMENT_XML.replace(
        "PEAJE-CUFE-0001", f"PEAJE-CUFE-{n:04d}"
    ).replace("FEUU2183418", f"FEUU218{n:04d}")


async def _ingest(n: int) -> str:
    result = await ingestion_service.process_xml_document(
        XMLDocument(file_name="peaje.zip", entry_name=f"peaje.zip/{n}.xml", xml_text=_peaje_xml(n)),
        persist=True,
        apply_ai=False,
        categories=[],
        cost_centers=[],
    )
    assert result["status"] == "created", result
    return str(result["factura_id"])


def _row(factura_id: str):
    with connection() as conn:
        factura = conn.execute(
            "select estado, total, iva from facturas where id = %s", (factura_id,)
        ).fetchone()
        items = conn.execute(
            "select descripcion, iva_porcentaje, cuenta_contable_alegra, "
            "centro_costo_alegra, prefill_source from items_factura where factura_id = %s",
            (factura_id,),
        ).fetchall()
        states = [
            r["estado"]
            for r in conn.execute(
                "select estado from causaciones where factura_id = %s order by created_at",
                (factura_id,),
            ).fetchall()
        ]
    return factura, items, states


@pytest.fixture
def alegra(monkeypatch):
    calls = {"bills": [], "fail": False}

    async def resolve(*args, **kwargs):
        return {"id": "7", "name": "DEVISAB S.A.S."}

    async def crear_bill(factura):
        calls["bills"].append(factura)
        if calls["fail"]:
            raise RemoteAPIError("rechazada por Alegra", status_code=400)
        return {"id": "bill-1"}

    monkeypatch.setattr(
        "services.factura_service.alegra_service.resolve_provider_contact", resolve
    )
    monkeypatch.setattr("services.factura_service.alegra_service.crear_bill", crear_bill)
    return calls


@pytest.mark.asyncio
async def test_peaje_flow_pending_then_authorized_then_rejected(alegra):
    save_config_cuenta(NIT, "DEVISAB S.A.S.", "5105", "12", 1, source="manual")

    # 1) Without opt-in: stays pending with description, IVA 0 and the rule's mapping.
    first = await _ingest(1)
    factura, items, _ = _row(first)
    assert factura["estado"] == "pendiente"
    assert float(factura["iva"]) == 0
    assert len(items) == 1
    assert items[0]["descripcion"] == PEAJE_DESCRIPTION
    assert float(items[0]["iva_porcentaje"]) == 0
    assert (items[0]["cuenta_contable_alegra"], items[0]["centro_costo_alegra"]) == ("5105", "12")
    assert items[0]["prefill_source"] == "manual"

    outcome = await auto_causacion_service.try_cause_from_imap_xml(first)
    assert outcome["status"] == "skipped"
    assert alegra["bills"] == []
    assert _row(first)[0]["estado"] == "pendiente"

    # 2) Opt-in: exactly one bill attempt with the configured mapping and XML data.
    save_config_cuenta(NIT, "DEVISAB S.A.S.", "5105", "12", 1, source="manual", auto_causar=True)
    second = await _ingest(2)
    outcome = await auto_causacion_service.try_cause_from_imap_xml(second)

    assert outcome["status"] == "caused"
    assert len(alegra["bills"]) == 1
    bill = alegra["bills"][0]
    assert bill.total == 13900 and bill.moneda == "COP" and bill.iva == 0
    assert [(i.cuenta_contable_alegra, i.centro_costo_alegra, i.iva_porcentaje, i.descripcion)
            for i in bill.items] == [("5105", "12", 0, PEAJE_DESCRIPTION)]
    factura, _, states = _row(second)
    assert factura["estado"] == "procesado"
    assert states == ["exitoso"]

    # 3) Alegra rejection: the invoice stays pending and visible, no duplicate attempt.
    alegra["fail"] = True
    third = await _ingest(3)
    outcome = await auto_causacion_service.try_cause_from_imap_xml(third)

    assert outcome["status"] == "pending"
    assert len(alegra["bills"]) == 2
    factura, _, states = _row(third)
    assert factura["estado"] == "pendiente"
    assert "autocausacion_bloqueada" in states
    assert "exitoso" not in states
