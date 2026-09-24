import pytest
from datetime import datetime, timezone

from services.factura_service import FacturaService
from services.ingestion_service import XMLDocument


@pytest.mark.asyncio
async def test_stats_accept_postgres_datetime(monkeypatch):
    class Repository:
        async def get_facturas_stats(self):
            return [
                {
                    "estado": "pendiente",
                    "created_at": datetime(2026, 9, 17, 12, tzinfo=timezone.utc),
                }
            ]

    monkeypatch.setattr(
        "services.factura_service.now_bogota",
        lambda: datetime(2026, 9, 17, 7, tzinfo=timezone.utc),
    )
    service = FacturaService(factura_repository=Repository())

    result = await service.get_facturas_stats()

    assert result == {"hoy": 1, "causadas": 0, "pendientes": 1, "errores": 0}


@pytest.mark.asyncio
async def test_preview_upload_facturas_summary(monkeypatch):
    service = FacturaService()

    docs = [
        XMLDocument(file_name="a.xml", entry_name="a.xml", xml_text="<xml/>"),
        XMLDocument(file_name="b.xml", entry_name="b.xml", xml_text="<xml/>"),
    ]

    async def fake_extract(files):
        return {
            "documents": docs,
            "errors": [
                {
                    "file_name": "bad.zip",
                    "entry_name": "bad.zip",
                    "status": "invalid",
                    "reason": "ZIP sin XML procesables.",
                }
            ],
        }

    async def fake_prefill_context(*, apply_ai):
        return {"categories": [], "cost_centers": []}

    async def fake_process(
        xml_doc,
        *,
        persist,
        apply_ai,
        categories,
        cost_centers,
        auto_apply_ai,
        preview_mode
    ):
        if xml_doc.entry_name == "a.xml":
            return {"status": "valid", "file_name": "a.xml", "entry_name": "a.xml"}
        return {
            "status": "duplicate",
            "file_name": "b.xml",
            "entry_name": "b.xml",
            "reason": "CUFE ya existe",
        }

    monkeypatch.setattr(
        "services.factura_service.ingestion_service.extract_xml_documents_from_upload",
        fake_extract,
    )
    monkeypatch.setattr(
        "services.factura_service.ingestion_service.build_prefill_context",
        fake_prefill_context,
    )
    monkeypatch.setattr(
        "services.factura_service.ingestion_service.process_xml_document", fake_process
    )

    result = await service.preview_upload_facturas(
        files=[object(), object()],
        apply_ai=False,
        auto_apply_ai=False,
    )

    assert result["summary"]["total_files"] == 2
    assert result["summary"]["total_xml"] == 2
    assert result["summary"]["valid"] == 1
    assert result["summary"]["duplicates"] == 1
    assert result["summary"]["invalid"] == 1
    assert len(result["files"]) == 3


def test_normalize_items_prefill_defaults():
    service = FacturaService()
    normalized = service._normalize_items_prefill(
        [
            {"descripcion": "x"},
            {"descripcion": "y", "prefill_source": None},
        ]
    )

    assert normalized[0]["prefill_source"] == "unknown"
    assert normalized[0]["confidence"] is None
    assert normalized[1]["prefill_source"] == "unknown"


@pytest.mark.asyncio
async def test_preview_upload_facturas_forwards_auto_apply_ai(monkeypatch):
    service = FacturaService()

    docs = [XMLDocument(file_name="a.xml", entry_name="a.xml", xml_text="<xml/>")]
    seen = {"auto_apply_ai": None}

    async def fake_extract(files):
        return {"documents": docs, "errors": []}

    async def fake_prefill_context(*, apply_ai):
        return {"categories": [], "cost_centers": []}

    async def fake_process(
        xml_doc,
        *,
        persist,
        apply_ai,
        categories,
        cost_centers,
        auto_apply_ai,
        preview_mode
    ):
        seen["auto_apply_ai"] = auto_apply_ai
        assert preview_mode is True
        return {"status": "valid", "file_name": "a.xml", "entry_name": "a.xml"}

    monkeypatch.setattr(
        "services.factura_service.ingestion_service.extract_xml_documents_from_upload",
        fake_extract,
    )
    monkeypatch.setattr(
        "services.factura_service.ingestion_service.build_prefill_context",
        fake_prefill_context,
    )
    monkeypatch.setattr(
        "services.factura_service.ingestion_service.process_xml_document", fake_process
    )

    await service.preview_upload_facturas(
        files=[object()], apply_ai=True, auto_apply_ai=True
    )
    assert seen["auto_apply_ai"] is True


class _NoopHttpContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


class _CausacionFakes:
    """Records the order of repository writes and Alegra calls."""

    def __init__(self, items):
        self.events = []
        self.factura = {
            "id": "f1",
            "estado": "pendiente",
            "cufe": "CUFE-1",
            "numero_factura": "F-1",
            "fecha_emision": "2026-09-14T10:00:00+00:00",
            "nit_proveedor": "900123456",
            "nombre_proveedor": "Proveedor",
            "nit_receptor": "800123000",
            "subtotal": 100,
            "iva": 0,
            "total": 100,
            "moneda": "COP",
            "items_factura": items,
        }
        outer = self

        class Factura:
            async def get_factura_with_items(self, factura_id):
                return dict(outer.factura)

            async def get_successful_causacion(self, factura_id):
                return None

            async def update_factura_fields(self, factura_id, payload):
                outer.events.append(("factura", payload))

            async def update_item_fields(self, item_id, payload):
                outer.events.append(("item", item_id, payload))

        class Causacion:
            async def save_causacion(self, payload):
                outer.events.append(("causacion", payload["estado"]))

        self.factura_repository = Factura()
        self.causacion_repository = Causacion()


def _causacion_service(fakes, monkeypatch):
    async def resolve(*args, **kwargs):
        return {"name": "Proveedor"}

    async def crear_bill(factura):
        fakes.events.append(("crear_bill", [i.centro_costo_alegra for i in factura.items]))
        return {"id": "bill-1"}

    async def no_mapping(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "services.factura_service.alegra_service.resolve_provider_contact", resolve
    )
    monkeypatch.setattr(
        "services.factura_service.alegra_service.crear_bill", crear_bill
    )
    monkeypatch.setattr(
        "services.factura_service.provider_mapping_service.compute_and_save_mapping",
        no_mapping,
    )
    return FacturaService(
        factura_repository=fakes.factura_repository,
        causacion_repository=fakes.causacion_repository,
        http_client_factory=lambda: _NoopHttpContext(),
    )


def _item(**overrides):
    return {
        "id": "i1",
        "descripcion": "Servicio",
        "cantidad": 1,
        "precio_unitario": 100,
        "descuento": 0,
        "iva_porcentaje": 0,
        "total_linea": 100,
        "cuenta_contable_alegra": "5105",
        "centro_costo_alegra": None,
        **overrides,
    }


@pytest.mark.asyncio
async def test_operator_correction_is_persisted_before_sending_to_alegra(monkeypatch):
    fakes = _CausacionFakes([_item()])
    service = _causacion_service(fakes, monkeypatch)

    await service.causar_factura(
        "f1",
        {"i1": {"cuenta_contable_alegra": "5105", "centro_costo_alegra": "12"}},
    )

    kinds = [event[0] for event in fakes.events]
    assert kinds.index("item") < kinds.index("crear_bill")
    assert (
        "item",
        "i1",
        {"cuenta_contable_alegra": "5105", "centro_costo_alegra": "12"},
    ) in fakes.events
    assert ("crear_bill", ["12"]) in fakes.events
    assert ("factura", {"estado": "procesado"}) in fakes.events


@pytest.mark.asyncio
async def test_loading_an_invoice_never_sends_it_to_alegra(monkeypatch):
    fakes = _CausacionFakes([_item(centro_costo_alegra="12")])
    service = _causacion_service(fakes, monkeypatch)

    await service.get_factura("f1")

    assert not [event for event in fakes.events if event[0] == "crear_bill"]


@pytest.mark.asyncio
async def test_causation_is_blocked_while_an_item_has_no_account(monkeypatch):
    from fastapi import HTTPException

    fakes = _CausacionFakes([_item(cuenta_contable_alegra=None)])
    service = _causacion_service(fakes, monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await service.causar_factura("f1", {})

    assert exc.value.detail["code"] == "REQUIERE_CONFIRMACION_MANUAL"
    assert not [event for event in fakes.events if event[0] == "crear_bill"]


@pytest.mark.asyncio
async def test_invoice_addressed_to_another_company_is_never_caused(monkeypatch):
    from fastapi import HTTPException
    from config import settings

    monkeypatch.setattr(settings, "COMPANY_NIT", "900741732")
    fakes = _CausacionFakes([_item(centro_costo_alegra="12")])
    service = _causacion_service(fakes, monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await service.causar_factura("f1", {})

    assert exc.value.detail["code"] == "NIT_RECEPTOR_NO_COINCIDE"
    assert not [event for event in fakes.events if event[0] == "crear_bill"]


@pytest.mark.asyncio
async def test_invoice_for_the_company_or_without_receptor_is_still_caused(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "COMPANY_NIT", "900741732")
    for receptor in ("900741732", None, "123456789"):
        fakes = _CausacionFakes([_item(centro_costo_alegra="12")])
        fakes.factura["nit_receptor"] = receptor
        service = _causacion_service(fakes, monkeypatch)

        await service.causar_factura("f1", {})

        assert [event for event in fakes.events if event[0] == "crear_bill"]


@pytest.mark.asyncio
async def test_pending_invoice_already_in_alegra_becomes_procesado(monkeypatch):
    fakes = _CausacionFakes([_item()])
    service = _causacion_service(fakes, monkeypatch)

    async def remote(**kwargs):
        return {"bill_id": "77"}

    monkeypatch.setattr(
        "services.factura_service.alegra_service.get_bill_accounting_by_invoice", remote
    )

    outcome = await service.marcar_si_ya_esta_en_alegra("f1")

    assert outcome["status"] == "already_in_alegra"
    assert ("factura", {"estado": "procesado"}) in fakes.events
    assert not [event for event in fakes.events if event[0] == "crear_bill"]


@pytest.mark.asyncio
async def test_pending_invoice_missing_in_alegra_stays_pending(monkeypatch):
    fakes = _CausacionFakes([_item()])
    service = _causacion_service(fakes, monkeypatch)

    async def remote(**kwargs):
        return None

    monkeypatch.setattr(
        "services.factura_service.alegra_service.get_bill_accounting_by_invoice", remote
    )

    assert (await service.marcar_si_ya_esta_en_alegra("f1"))["status"] == "pending"
    assert not [event for event in fakes.events if event[0] == "factura"]
