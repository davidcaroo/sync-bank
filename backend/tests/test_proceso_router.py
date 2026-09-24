import pytest
from fastapi.testclient import TestClient

import main
from services import sync_job_service


@pytest.fixture
def client(monkeypatch):
    for name in (
        "open_pool",
        "close_pool",
        "start_scheduler",
        "apply_schema_upgrades",
        "start_sync_runner",
        "stop_sync_runner",
    ):
        monkeypatch.setattr(main, name, lambda: None)
    with TestClient(main.app, follow_redirects=False) as c:
        c.auth = ("admin", "test")
        yield c


def test_manual_trigger_answers_202_without_reading_the_mailbox(client, monkeypatch):
    async def enqueue(requested_by):
        assert requested_by == "manual"
        job = {"id": "j1", "status": "pending", "requested_by": "manual"}
        return {"job": job, "created": True}

    async def forbidden(*args, **kwargs):
        raise AssertionError("IMAP must not run inside the request")

    monkeypatch.setattr(sync_job_service, "enqueue", enqueue)
    monkeypatch.setattr(sync_job_service, "check_emails", forbidden)

    response = client.post("/api/proceso/manual")

    assert response.status_code == 202
    assert response.json() == {
        "job": {"id": "j1", "status": "pending", "requested_by": "manual"},
        "created": True,
    }


def test_status_comes_from_the_persisted_job(client, monkeypatch):
    job = {
        "id": "j1",
        "status": "succeeded",
        "progress": {},
        "result": {"created": 2},
        "finished_at": "2026-09-24T18:00:00+00:00",
        "started_at": "2026-09-24T17:59:00+00:00",
    }
    monkeypatch.setattr(sync_job_service, "current_status", lambda: job)

    body = client.get("/api/proceso/status").json()

    assert body["job"]["status"] == "succeeded"
    assert body["summary"] == {"created": 2}
    assert body["last_execution"] == "2026-09-24T18:00:00+00:00"


def test_status_without_any_job_is_empty(client, monkeypatch):
    monkeypatch.setattr(sync_job_service, "current_status", lambda: None)

    assert client.get("/api/proceso/status").json() == {
        "job": None,
        "summary": {},
        "last_execution": None,
    }
