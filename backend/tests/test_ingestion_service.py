import pytest

from services.ingestion_service import IngestionService, XMLDocument


class DummyItem:
    def __init__(self):
        self.descripcion = "Servicio"
        self.cantidad = 1
        self.precio_unitario = 100
        self.descuento = 0
        self.iva_porcentaje = 19
        self.total_linea = 100
        self.cuenta_contable_alegra = None
        self.centro_costo_alegra = None


class DummyFactura:
    def __init__(self):
        self.cufe = "CUFE-1"
        self.numero_factura = "F-1"
        self.fecha_emision = None
        self.nit_proveedor = "9001"
        self.nombre_proveedor = "Proveedor"
        self.subtotal = 100
        self.iva = 19
        self.rete_fuente = 0
        self.rete_ica = 0
        self.rete_iva = 0
        self.total = 119
        self.moneda = "COP"
        self.items = [DummyItem()]

    def model_dump(self, exclude=None, mode=None):
        return {
            "cufe": self.cufe,
            "numero_factura": self.numero_factura,
            "fecha_emision": self.fecha_emision,
            "nit_proveedor": self.nit_proveedor,
            "nombre_proveedor": self.nombre_proveedor,
            "subtotal": self.subtotal,
            "iva": self.iva,
            "rete_fuente": self.rete_fuente,
            "rete_ica": self.rete_ica,
            "rete_iva": self.rete_iva,
            "total": self.total,
            "moneda": self.moneda,
        }


@pytest.mark.asyncio
async def test_ingestion_prefills_with_config(monkeypatch):
    svc = IngestionService()

    def fake_parse_xml(_):
        return DummyFactura()

    async def fake_run_in_executor(action):
        return action()

    monkeypatch.setattr("services.ingestion_service.parse_xml_dian", fake_parse_xml)
    monkeypatch.setattr(
        "services.ingestion_service.run_in_executor", fake_run_in_executor
    )
    monkeypatch.setattr(
        "services.ingestion_service.get_config_cuenta",
        lambda nit: {"id_cuenta_alegra": "5001"},
    )
    monkeypatch.setattr(
        "services.ingestion_service.sync_config_proveedor_nombre",
        lambda nit, nombre: None,
    )
    monkeypatch.setattr(
        "services.ingestion_service.find_factura_by_cufe", lambda cufe: None
    )
    monkeypatch.setattr(
        "services.ingestion_service.save_factura",
        lambda data, items: {"factura_id": "1", "duplicado": False},
    )

    xml_doc = XMLDocument(file_name="x.xml", entry_name="x.xml", xml_text="<xml/>")
    result = await svc.process_xml_document(
        xml_doc,
        persist=False,
        apply_ai=False,
        categories=[],
        cost_centers=[],
    )

    items = result["factura_preview"]["items"]
    assert items[0]["cuenta_contable_alegra"] == "5001"


def _patch_common(monkeypatch, config):
    async def fake_run_in_executor(action):
        return action()

    monkeypatch.setattr(
        "services.ingestion_service.parse_xml_dian", lambda _: DummyFactura()
    )
    monkeypatch.setattr(
        "services.ingestion_service.run_in_executor", fake_run_in_executor
    )
    monkeypatch.setattr(
        "services.ingestion_service.get_config_cuenta", lambda nit: config
    )
    monkeypatch.setattr(
        "services.ingestion_service.sync_config_proveedor_nombre",
        lambda nit, nombre: None,
    )
    monkeypatch.setattr(
        "services.ingestion_service.find_factura_by_cufe", lambda cufe: None
    )


async def _preview_items():
    xml_doc = XMLDocument(file_name="x.xml", entry_name="x.xml", xml_text="<xml/>")
    result = await IngestionService().process_xml_document(
        xml_doc, persist=False, apply_ai=False, categories=[], cost_centers=[]
    )
    return result["factura_preview"]["items"]


@pytest.mark.asyncio
async def test_manual_rule_prefills_account_and_cost_center(monkeypatch):
    _patch_common(
        monkeypatch,
        {
            "id_cuenta_alegra": "5105",
            "id_centro_costo_alegra": "12",
            "source": "manual",
            "confianza": 1,
        },
    )

    item = (await _preview_items())[0]

    assert item["cuenta_contable_alegra"] == "5105"
    assert item["centro_costo_alegra"] == "12"
    assert item["prefill_source"] == "manual"
    assert item["confidence"] == 1.0


@pytest.mark.asyncio
async def test_historical_suggestion_prefills_account_and_cost_center(monkeypatch):
    _patch_common(monkeypatch, None)

    async def fake_suggestion(*args, **kwargs):
        return {"cuenta": "5105", "centro_costo": "12", "confidence": 0.75}

    monkeypatch.setattr(
        "services.provider_mapping_service.provider_mapping_service."
        "suggest_mapping_from_history",
        fake_suggestion,
    )

    item = (await _preview_items())[0]

    assert item["cuenta_contable_alegra"] == "5105"
    assert item["centro_costo_alegra"] == "12"
    assert item["prefill_source"] == "historical"
    assert item["confidence"] == 0.75


@pytest.mark.asyncio
async def test_unmapped_provider_gets_no_invented_classification(monkeypatch):
    _patch_common(monkeypatch, None)

    async def no_suggestion(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "services.provider_mapping_service.provider_mapping_service."
        "suggest_mapping_from_history",
        no_suggestion,
    )

    item = (await _preview_items())[0]

    assert item["cuenta_contable_alegra"] is None
    assert item["centro_costo_alegra"] is None
    assert item["prefill_source"] == "none"


def test_peaje_zip_yields_only_the_xml_document():
    from peaje_fixture import peaje_zip_bytes
    from services.ingestion.extractor import IngestionExtractor

    result = IngestionExtractor().extract_xml_documents_from_attachment(
        "peaje.zip", peaje_zip_bytes()
    )

    assert [doc.entry_name for doc in result["documents"]] == [
        "peaje.zip/factura.xml"
    ]
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_invoice_issued_before_min_issue_date_is_ignored(monkeypatch):
    from datetime import datetime
    from types import SimpleNamespace

    from config import settings
    from services.ingestion.processor import IngestionProcessor

    monkeypatch.setattr(settings, "MIN_ISSUE_DATE", "2026-09-01")
    old = SimpleNamespace(fecha_emision=datetime(2025, 12, 31))
    processor = IngestionProcessor(
        parse_xml=lambda _xml: old,
        factura_repository=None,
        provider_config_repository=None,
    )
    doc = SimpleNamespace(xml_text="<x/>", file_name="a.zip", entry_name="a.xml")

    result = await processor.process_xml_document(
        doc, persist=True, apply_ai=False, categories=[], cost_centers=[]
    )

    assert result["status"] == "ignored"
