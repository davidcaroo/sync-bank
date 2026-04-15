import pytest
from fastapi import HTTPException

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

    async def fake_process(xml_doc, *, persist, apply_ai, categories, cost_centers, auto_apply_ai, preview_mode):
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
    normalized = service._normalize_items_prefill([
        {"descripcion": "x"},
        {"descripcion": "y", "prefill_source": None},
    ])

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

    async def fake_process(xml_doc, *, persist, apply_ai, categories, cost_centers, auto_apply_ai, preview_mode):
        seen["auto_apply_ai"] = auto_apply_ai
        assert preview_mode is True
        return {"status": "valid", "file_name": "a.xml", "entry_name": "a.xml"}

    monkeypatch.setattr("services.factura_service.ingestion_service.extract_xml_documents_from_upload", fake_extract)
    monkeypatch.setattr("services.factura_service.ingestion_service.build_prefill_context", fake_prefill_context)
    monkeypatch.setattr("services.factura_service.ingestion_service.process_xml_document", fake_process)

    await service.preview_upload_facturas(files=[object()], apply_ai=True, auto_apply_ai=True)
    assert seen["auto_apply_ai"] is True


class _FakeFacturaRepository:
    async def get_factura_with_items(self, factura_id):
        return {"id": factura_id}


@pytest.mark.asyncio
async def test_enqueue_causar_factura_creates_job(monkeypatch):
    service = FacturaService(factura_repository=_FakeFacturaRepository())

    async def fake_run_in_executor(action):
        return action()

    monkeypatch.setattr("services.factura_service.run_in_executor", fake_run_in_executor)
    monkeypatch.setattr(
        "services.factura_service.create_or_get_job",
        lambda **kwargs: {"id": "job-1", "status": "queued", "created": True},
    )

    dispatched = {}

    def fake_enqueue_causar_factura(*, job_id, factura_id, overrides_map=None):
        dispatched["job_id"] = job_id
        dispatched["factura_id"] = factura_id
        dispatched["overrides_map"] = overrides_map or {}

    monkeypatch.setattr("services.factura_service.enqueue_causar_factura", fake_enqueue_causar_factura)

    result = await service.enqueue_causar_factura("factura-1", {"item": {"cuenta_contable_alegra": "5001"}})

    assert result["job_id"] == "job-1"
    assert result["created"] is True
    assert dispatched["factura_id"] == "factura-1"


@pytest.mark.asyncio
async def test_get_job_status_404(monkeypatch):
    service = FacturaService(factura_repository=_FakeFacturaRepository())

    async def fake_run_in_executor(action):
        return action()

    monkeypatch.setattr("services.factura_service.run_in_executor", fake_run_in_executor)
    monkeypatch.setattr("services.factura_service.repo_get_job", lambda _job_id: None)

    with pytest.raises(HTTPException) as exc:
        await service.get_job_status("missing")

    assert exc.value.status_code == 404