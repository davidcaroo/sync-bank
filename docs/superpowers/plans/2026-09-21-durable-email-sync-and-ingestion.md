# Durable Email Sync and Safe Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist email synchronization as recoverable PostgreSQL jobs and accept only safe DIAN invoice XML addressed to LOGINCARGO.

**Architecture:** Keep the FastAPI monolith and use PostgreSQL as the durable queue. A small in-process runner claims jobs atomically; both APScheduler and the manual endpoint enqueue the same job type. The existing ingestion pipeline gains document-type, ZIP-resource and receiver-NIT validation before persistence or autocausation.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3, PostgreSQL 16, APScheduler, React/Vite, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-21-durable-email-sync-and-ingestion-design.md`

## Global Constraints

- No Redis, RabbitMQ, new microservice or AI dependency.
- PostgreSQL is the source of truth for job state.
- `COMPANY_NIT=900741732` in production; receiver validation is mandatory for persisted XML.
- Automatic causation remains limited to authorized manual provider rules.
- Automated verification must not cause a real invoice in Alegra.

## Review Focus

- Two simultaneous manual requests must return the same active job and execute IMAP once; Task 2 tests this.
- A process crash after claiming a job must not leave it permanently running; Task 2 tests recovery.
- A ZIP bomb or encrypted ZIP must be rejected before decompression; Task 3 tests both.
- An `AttachedDocument` containing an invoice plus `ApplicationResponse` must yield only the invoice; Task 3 tests this.
- Missing or formatted receiver NIT values must fail or normalize predictably; Task 4 tests both.

---

### Task 1: Persisted job repository and schema

**Files:**
- Modify: `database/schema.sql`
- Modify: `backend/repositories/schema_upgrades.py`
- Create: `backend/repositories/sync_job_repository.py`
- Create: `backend/tests/integration/test_sync_job_repository_postgres.py`

**Interfaces:**
- Produces: `enqueue_email_sync(requested_by) -> dict`, `claim_next_email_sync() -> dict | None`, `finish_job(job_id, result)`, `retry_or_fail_job(job_id, error)`, `recover_interrupted_jobs()`, `get_sync_status() -> dict | None`.

- [ ] Write integration tests proving one active job, exclusive claiming, persisted completion, three-attempt failure and recovery of interrupted work.
- [ ] Run `python -m pytest tests/integration/test_sync_job_repository_postgres.py -q` from `backend`; expect failures because the table/repository do not exist.
- [ ] Add `sync_jobs`, its active-job partial unique index and idempotent startup migration.
- [ ] Implement the repository with short transactions and `FOR UPDATE SKIP LOCKED`.
- [ ] Re-run the integration test; expect all tests to pass.
- [ ] Commit with `feat: persist email synchronization jobs`.

### Task 2: Runner, scheduler and non-blocking API

**Files:**
- Create: `backend/services/sync_job_service.py`
- Modify: `backend/routers/proceso.py`
- Modify: `backend/scheduler.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_sync_job_service.py`
- Modify: `backend/tests/test_facturas_router.py` or create `backend/tests/test_proceso_router.py`

**Interfaces:**
- Consumes Task 1 repository functions.
- Produces: `sync_job_service.enqueue(requested_by)`, `sync_job_service.run_pending()`, `sync_job_service.recover()` and HTTP responses `{job, created}` plus persisted status.

- [ ] Write tests showing the manual endpoint returns `202` before `check_emails` completes, duplicate requests share one job, the scheduler enqueues instead of processing inline, and successful/failed attempts update PostgreSQL through the repository contract.
- [ ] Run the focused tests; expect failures because the runner and response contract do not exist.
- [ ] Implement a single wakeable runner task, recovery on startup and scheduler enqueueing.
- [ ] Replace module globals in `proceso.py` with repository-backed status.
- [ ] Re-run focused tests; expect all to pass.
- [ ] Commit with `feat: run email synchronization in durable background jobs`.

### Task 3: Safe ZIP and DIAN document extraction

**Files:**
- Modify: `backend/services/ingestion/extractor.py`
- Modify: `backend/services/email_service.py`
- Modify: `backend/config.py`
- Modify: `.env.example`
- Modify: `backend/tests/test_ingestion_service.py`
- Modify: `backend/tests/test_email_mailbox.py`

**Interfaces:**
- Produces validated `XMLDocument` objects only for standalone `Invoice` or `AttachedDocument` containing an invoice; extraction errors retain file and entry names.

- [ ] Add tests for standalone invoice, attached invoice, ignored application response, unsupported credit/debit note, encrypted ZIP, excessive entries, expansion limit, nesting limit and XML+PDF avoiding OCR.
- [ ] Run focused tests; expect failures for document filtering, ZIP limits and PDF prioritization.
- [ ] Add configuration limits with conservative defaults: 20 MiB attachment, 100 ZIP entries, 50 MiB expanded data, compression ratio 100 and depth 3.
- [ ] Validate ZIP metadata before reading entries and classify XML roots with `lxml` without adding dependencies.
- [ ] Enumerate email attachments first; if XML/ZIP exists, process those and retain/ignore companion PDF without OCR.
- [ ] Re-run focused tests; expect all to pass.
- [ ] Commit with `fix: accept only safe DIAN invoice attachments`.

### Task 4: Mandatory company receiver validation

**Files:**
- Modify: `backend/config.py`
- Modify: `.env.example`
- Modify: `backend/services/xml_parser.py`
- Modify: `backend/services/ingestion/processor.py`
- Modify: `backend/services/auto_causacion_service.py`
- Modify: `backend/tests/test_xml_parser.py`
- Modify: `backend/tests/test_ingestion_service.py`
- Modify: `backend/tests/test_auto_causacion_service.py`

**Interfaces:**
- Produces: parser returns an empty receiver when absent; ingestion returns `invalid` with `missing_receiver_nit` or `receiver_nit_mismatch`; autocausation independently refuses mismatches.

- [ ] Add tests for missing receiver, formatted correct NIT, incorrect NIT and autocausation defense in depth.
- [ ] Run focused tests; expect failures because the parser currently invents `123456789` and ingestion does not compare the company NIT.
- [ ] Add required `COMPANY_NIT`, remove the fallback and validate before persistence.
- [ ] Add the same receiver guard to autocausation.
- [ ] Re-run focused tests; expect all to pass.
- [ ] Commit with `fix: validate invoice receiver before ingestion`.

### Task 5: Persistent progress in the dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`
- Modify: `frontend/src/lib/api.js`
- Create: `frontend/tests/sync-job-status.test.mjs`

**Interfaces:**
- Consumes Task 2 response and status objects.
- Produces polling that continues after remount/reload while status is `pending` or `running`, and renders terminal result/error.

- [ ] Add frontend contract tests for accepted jobs, active polling state and terminal summaries.
- [ ] Run `npm test -- --run`; expect the new tests to fail.
- [ ] Update API helpers and dashboard state to poll persisted status without keeping the POST request open.
- [ ] Re-run frontend tests, lint and build; expect success.
- [ ] Commit with `feat: show durable email synchronization progress`.

### Task 6: Full verification and production rollout

**Files:**
- Modify: `README.md`
- Modify: Railway production variables (external configuration)

**Interfaces:**
- Consumes all prior tasks.
- Produces deployed schema, `COMPANY_NIT=900741732`, healthy API and non-destructive smoke evidence.

- [ ] Update README with job states, recovery, ZIP limits and receiver validation.
- [ ] Run backend unit and PostgreSQL integration suite; expect zero failures.
- [ ] Run frontend tests, lint and build; expect zero failures.
- [ ] Commit with `docs: describe durable invoice synchronization`.
- [ ] Push `main`, set `COMPANY_NIT=900741732` in Railway and deploy.
- [ ] Smoke-test `/healthz`, enqueue/status behavior and configuration/catalog endpoints without causing any real invoice.
- [ ] Verify `main`, `origin/main` and deployed revision match.
