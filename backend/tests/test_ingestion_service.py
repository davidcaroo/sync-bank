import pytest
from types import SimpleNamespace

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
    monkeypatch.setattr("services.ingestion_service.run_in_executor", fake_run_in_executor)
    monkeypatch.setattr("services.ingestion_service.get_config_cuenta", lambda nit: {"id_cuenta_alegra": "5001"})
    monkeypatch.setattr("services.ingestion_service.sync_config_proveedor_nombre", lambda nit, nombre: None)
    monkeypatch.setattr("services.ingestion_service.find_factura_by_cufe", lambda cufe: None)
    monkeypatch.setattr("services.ingestion_service.save_factura", lambda data, items: {"factura_id": "1", "duplicado": False})

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
