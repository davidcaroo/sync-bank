import os

os.environ.setdefault("IMAP_USER", "test")
os.environ.setdefault("IMAP_PASS", "test")
os.environ.setdefault("ALEGRA_EMAIL", "test@example.com")
os.environ.setdefault("ALEGRA_TOKEN", "token")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service")

from services.pdf_ingestion_service import PdfIngestionService


def test_build_factura_model_defaults():
    service = PdfIngestionService()
    payload = {
        "numero_factura": "INV-1",
        "nit_proveedor": "900123456",
        "nombre_proveedor": "Proveedor Test",
        "items": [
            {
                "descripcion": "Servicio",
                "cantidad": 2,
                "precio_unitario": 1000,
                "total_linea": 2000,
            }
        ],
    }

    factura = service._build_factura_model(payload)
    assert factura.numero_factura == "INV-1"
    assert factura.nit_proveedor == "900123456"
    assert factura.nombre_proveedor == "Proveedor Test"
    assert factura.moneda == "COP"
    assert factura.items
    assert factura.items[0].descripcion == "Servicio"
