import pytest

from services.factura_service import FacturaService
from services.ingestion_service import XMLDocument


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

    async def fake_process(xml_doc, *, persist, apply_ai, categories, cost_centers):
        if xml_doc.entry_name == "a.xml":
            return {"status": "valid", "file_name": "a.xml", "entry_name": "a.xml"}
        return {
            "status": "duplicate",
            "file_name": "b.xml",
            "entry_name": "b.xml",
            "reason": "CUFE ya existe",
        }

    monkeypatch.setattr("services.factura_service.ingestion_service.extract_xml_documents_from_upload", fake_extract)
    monkeypatch.setattr("services.factura_service.ingestion_service.build_prefill_context", fake_prefill_context)
    monkeypatch.setattr("services.factura_service.ingestion_service.process_xml_document", fake_process)

    result = await service.preview_upload_facturas(files=[object(), object()], apply_ai=False)

    assert result["summary"]["total_files"] == 2
    assert result["summary"]["total_xml"] == 2
    assert result["summary"]["valid"] == 1
    assert result["summary"]["duplicates"] == 1
    assert result["summary"]["invalid"] == 1
    assert len(result["files"]) == 3


def test_normalize_items_prefill_defaults():
    service = FacturaService()
    normalized = service._normalize_items_prefill([
        {"descripcion": "x"},
        {"descripcion": "y", "prefill_source": None},
    ])

    assert normalized[0]["prefill_source"] == "unknown"
    assert normalized[0]["confidence"] is None
    assert normalized[1]["prefill_source"] == "unknown"