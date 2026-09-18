import os

os.environ.setdefault("IMAP_USER", "test")
os.environ.setdefault("IMAP_PASS", "test")
os.environ.setdefault("ALEGRA_EMAIL", "test@example.com")
os.environ.setdefault("ALEGRA_TOKEN", "token")

import pytest

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


class _ConfigRepo:
    def __init__(self, config):
        self._config = config

    async def get_config_cuenta(self, nit):
        return self._config


def _pdf_service(config):
    service = PdfIngestionService()
    service._provider_config_repository = _ConfigRepo(config)
    return service


async def _prefill(service):
    factura = service._build_factura_model(
        {
            "numero_factura": "INV-1",
            "nit_proveedor": "900123456",
            "items": [
                {"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 10}
            ],
        }
    )
    saved, preview = await service._prefill_items(
        factura,
        apply_ai=False,
        auto_apply_ai=False,
        categories=[],
        cost_centers=[],
        preview_mode=True,
    )
    return saved[0], preview[0]


@pytest.mark.asyncio
async def test_pdf_manual_rule_prefills_account_and_cost_center():
    saved, preview = await _prefill(
        _pdf_service(
            {
                "id_cuenta_alegra": "5105",
                "id_centro_costo_alegra": "12",
                "source": "manual",
                "confianza": 1,
            }
        )
    )

    for item in (saved, preview):
        assert item["cuenta_contable_alegra"] == "5105"
        assert item["centro_costo_alegra"] == "12"
        assert item["prefill_source"] == "manual"
        assert item["confidence"] == 1.0


@pytest.mark.asyncio
async def test_pdf_historical_suggestion_prefills_cost_center(monkeypatch):
    async def fake_suggestion(*args, **kwargs):
        return {"cuenta": "5105", "centro_costo": "12", "confidence": 0.75}

    monkeypatch.setattr(
        "services.pdf_ingestion_service.provider_mapping_service."
        "suggest_mapping_from_history",
        fake_suggestion,
    )

    saved, _ = await _prefill(_pdf_service(None))

    assert saved["cuenta_contable_alegra"] == "5105"
    assert saved["centro_costo_alegra"] == "12"
    assert saved["prefill_source"] == "historical"
