import pytest

from routers.facturas import preview_upload_facturas, router


@pytest.mark.asyncio
async def test_preview_upload_accepts_auto_apply_ai(monkeypatch):
    captured = {"apply_ai": None, "auto_apply_ai": None}

    async def fake_preview(files, *, apply_ai=True, auto_apply_ai=False):
        captured["apply_ai"] = apply_ai
        captured["auto_apply_ai"] = auto_apply_ai
        return {"summary": {}, "files": []}

    monkeypatch.setattr("routers.facturas.factura_service.preview_upload_facturas", fake_preview)

    response = await preview_upload_facturas(
        files=[object()],
        apply_ai=True,
        auto_apply_ai=True,
    )

    assert response == {"summary": {}, "files": []}
    assert captured["apply_ai"] is True
    assert captured["auto_apply_ai"] is True


def test_async_job_routes_are_not_registered():
    paths = {route.path for route in router.routes}

    assert "/facturas/jobs/{job_id}" not in paths
    assert "/facturas/{factura_id}/causar-async" not in paths
    assert "/facturas/{factura_id}/causar" in paths
