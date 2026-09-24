from concurrent.futures import ThreadPoolExecutor

import pytest

from repositories.database import transaction
from repositories.sync_job_repository import (
    claim_next_email_sync,
    enqueue_email_sync,
    finish_job,
    get_sync_status,
    recover_interrupted_jobs,
    retry_or_fail_job,
    update_progress,
)


@pytest.fixture(autouse=True)
def clean_jobs():
    with transaction() as conn:
        conn.execute("delete from sync_jobs")


def test_only_one_active_job_exists_and_a_finished_one_allows_a_new_job():
    first = enqueue_email_sync("manual")
    again = enqueue_email_sync("scheduler")

    assert first["created"] is True and again["created"] is False
    assert first["job"]["id"] == again["job"]["id"]
    assert first["job"]["requested_by"] == "manual"

    claimed = claim_next_email_sync()
    assert enqueue_email_sync("manual")["job"]["id"] == claimed["id"]

    finish_job(claimed["id"], {"created": 1})
    fresh = enqueue_email_sync("scheduler")
    assert fresh["created"] is True and fresh["job"]["id"] != claimed["id"]


def test_two_consumers_never_claim_the_same_job():
    enqueue_email_sync("manual")

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim_next_email_sync(), range(2)))

    assert len([c for c in claims if c]) == 1
    winner = next(c for c in claims if c)
    assert winner["status"] == "running" and winner["attempts"] == 1
    assert winner["started_at"] is not None


def test_completion_and_progress_are_persisted_and_readable_as_status():
    job = enqueue_email_sync("manual")["job"]
    claim_next_email_sync()

    update_progress(job["id"], {"processed": 5, "total": 20})
    running = get_sync_status()
    assert running["status"] == "running"
    assert running["progress"] == {"processed": 5, "total": 20}

    finish_job(job["id"], {"created": 3, "duplicates": 2})
    done = get_sync_status()
    assert done["status"] == "succeeded"
    assert done["result"] == {"created": 3, "duplicates": 2}
    assert done["finished_at"] is not None


def test_status_prefers_the_active_job_over_the_last_finished_one():
    old = enqueue_email_sync("manual")["job"]
    claim_next_email_sync()
    finish_job(old["id"], {})

    queued = enqueue_email_sync("scheduler")["job"]

    assert get_sync_status()["id"] == queued["id"]


def test_a_job_is_retried_up_to_three_attempts_then_fails_with_the_last_error():
    job = enqueue_email_sync("manual")["job"]

    for attempt in (1, 2):
        assert claim_next_email_sync()["attempts"] == attempt
        assert retry_or_fail_job(job["id"], f"imap down {attempt}") == "pending"

    assert claim_next_email_sync()["attempts"] == 3
    assert retry_or_fail_job(job["id"], "imap down 3") == "failed"

    status = get_sync_status()
    assert status["status"] == "failed"
    assert status["error_message"] == "imap down 3"
    assert claim_next_email_sync() is None


def test_jobs_left_running_by_a_restart_go_back_to_the_queue_or_fail():
    job = enqueue_email_sync("manual")["job"]
    claim_next_email_sync()

    assert recover_interrupted_jobs() == 1
    assert get_sync_status()["status"] == "pending"

    with transaction() as conn:
        conn.execute(
            "update sync_jobs set status = 'running', attempts = 3 where id = %s",
            (job["id"],),
        )
    assert recover_interrupted_jobs() == 1
    status = get_sync_status()
    assert status["status"] == "failed"
    assert "interrumpido" in status["error_message"].lower()
