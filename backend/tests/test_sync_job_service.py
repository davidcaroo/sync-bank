import itertools

import pytest

from services import sync_job_service


class FakeJobs:
    """In-memory stand-in for sync_job_repository with the same contract."""

    def __init__(self):
        self.jobs = []
        self._ids = itertools.count(1)

    def _active(self):
        return next((j for j in self.jobs if j["status"] in ("pending", "running")), None)

    def enqueue_email_sync(self, requested_by):
        active = self._active()
        if active:
            return {"job": active, "created": False}
        job = {
            "id": next(self._ids),
            "status": "pending",
            "attempts": 0,
            "max_attempts": 3,
            "requested_by": requested_by,
            "progress": {},
            "result": None,
            "error_message": None,
        }
        self.jobs.append(job)
        return {"job": job, "created": True}

    def claim_next_email_sync(self):
        job = next((j for j in self.jobs if j["status"] == "pending"), None)
        if job:
            job.update(status="running", attempts=job["attempts"] + 1)
        return job

    def update_progress(self, job_id, progress):
        self._get(job_id)["progress"] = progress

    def finish_job(self, job_id, result):
        self._get(job_id).update(status="succeeded", result=result)

    def retry_or_fail_job(self, job_id, error):
        job = self._get(job_id)
        job["error_message"] = error
        job["status"] = "pending" if job["attempts"] < job["max_attempts"] else "failed"
        return job["status"]

    def recover_interrupted_jobs(self):
        return 0

    def get_sync_status(self):
        return self._active() or (self.jobs[-1] if self.jobs else None)

    def _get(self, job_id):
        return next(j for j in self.jobs if j["id"] == job_id)


@pytest.fixture
def jobs(monkeypatch):
    fake = FakeJobs()
    for name in (
        "enqueue_email_sync",
        "claim_next_email_sync",
        "update_progress",
        "finish_job",
        "retry_or_fail_job",
        "recover_interrupted_jobs",
        "get_sync_status",
    ):
        monkeypatch.setattr(sync_job_service.repo, name, getattr(fake, name))
    monkeypatch.setattr(sync_job_service, "RETRY_DELAY_SECONDS", 0)
    return fake


def _mailbox(monkeypatch, outcomes):
    calls = []

    async def check_emails(search_criteria="UNSEEN", on_progress=None):
        calls.append(search_criteria)
        if on_progress:
            await on_progress({"messages_found": 4, "messages_processed": 2})
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(sync_job_service, "check_emails", check_emails)
    return calls


@pytest.mark.asyncio
async def test_a_successful_run_stores_the_summary_and_reports_progress(jobs, monkeypatch):
    calls = _mailbox(monkeypatch, [{"created": 3, "errors": 0}])
    await sync_job_service.enqueue("scheduler")

    await sync_job_service.run_pending()

    job = jobs.jobs[0]
    assert job["status"] == "succeeded" and job["result"]["created"] == 3
    assert job["progress"] == {"messages_found": 4, "messages_processed": 2}
    assert calls == ["UNSEEN"]


@pytest.mark.asyncio
async def test_a_manual_run_rescans_the_mailbox_since_the_minimum_issue_date(
    jobs, monkeypatch
):
    monkeypatch.setattr(sync_job_service.settings, "MIN_ISSUE_DATE", "2026-09-01")
    calls = _mailbox(monkeypatch, [{"created": 0}])
    await sync_job_service.enqueue("manual")

    await sync_job_service.run_pending()

    assert calls == ["SINCE 01-Sep-2026"]


@pytest.mark.asyncio
async def test_duplicate_requests_share_one_job_and_read_the_mailbox_once(
    jobs, monkeypatch
):
    calls = _mailbox(monkeypatch, [{"created": 1}])

    first = await sync_job_service.enqueue("manual")
    second = await sync_job_service.enqueue("scheduler")
    await sync_job_service.run_pending()

    assert first["created"] is True and second["created"] is False
    assert first["job"]["id"] == second["job"]["id"]
    assert len(jobs.jobs) == 1 and len(calls) == 1


@pytest.mark.asyncio
async def test_a_transient_imap_failure_is_retried_three_times_then_fails(
    jobs, monkeypatch
):
    calls = _mailbox(monkeypatch, [{"errors": 1, "fatal_error": "imap down"}])
    await sync_job_service.enqueue("scheduler")

    await sync_job_service.run_pending()

    job = jobs.jobs[0]
    assert len(calls) == 3
    assert job["status"] == "failed" and job["error_message"] == "imap down"


@pytest.mark.asyncio
async def test_an_unexpected_exception_counts_as_a_failed_attempt(jobs, monkeypatch):
    _mailbox(monkeypatch, [RuntimeError("boom"), {"created": 2}])
    await sync_job_service.enqueue("scheduler")

    await sync_job_service.run_pending()

    job = jobs.jobs[0]
    assert job["status"] == "succeeded" and job["attempts"] == 2


@pytest.mark.asyncio
async def test_document_errors_do_not_retry_the_whole_job(jobs, monkeypatch):
    calls = _mailbox(monkeypatch, [{"created": 1, "invalid": 2, "errors": 1}])
    await sync_job_service.enqueue("scheduler")

    await sync_job_service.run_pending()

    assert len(calls) == 1 and jobs.jobs[0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_the_scheduler_only_enqueues_and_never_reads_the_mailbox(jobs, monkeypatch):
    calls = _mailbox(monkeypatch, [{"created": 1}])

    await sync_job_service.enqueue_scheduled()

    assert calls == [] and jobs.jobs[0]["requested_by"] == "scheduler"
