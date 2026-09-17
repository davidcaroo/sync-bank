# PostgreSQL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace backend access through Supabase Data API with transactional PostgreSQL access while preserving existing HTTP and service behavior.

**Architecture:** Keep the current repository function signatures to limit blast radius, but implement them with a shared `psycopg_pool.ConnectionPool`. Capture the real `public` schema from Supabase, restore it into local PostgreSQL, make invoice writes atomic, verify data parity, and only then remove server-side Supabase dependencies.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3, psycopg-pool, PostgreSQL 16, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-17-sync-bank-architecture-design.md`

## Global Constraints

- Preserve all current HTTP response shapes during this plan.
- Do not modify or discard unrelated uncommitted work.
- Use parameterized SQL only.
- Use `Decimal` in new monetary database boundaries; do not introduce new `float` conversions.
- Write invoice and items in one transaction.
- Keep CUFE idempotency enforced by PostgreSQL.
- PostgreSQL is server-only; no browser connection string.
- Do not introduce an ORM or migration framework.
- Python runtime remains 3.11.
- Every task ends with its focused tests and a dedicated commit.

---

## File Map

### Create

- `database/schema.sql`: canonical schema captured from the live `public` schema and made portable.
- `database/verify.sql`: parity queries used before and after cutover.
- `docker-compose.test.yml`: disposable PostgreSQL 16 used by repository integration tests.
- `backend/repositories/database.py`: shared connection pool and transaction helpers.
- `backend/tests/integration/conftest.py`: database reset fixture.
- `backend/tests/integration/test_factura_repository_postgres.py`: atomicity and idempotency checks.
- `backend/tests/integration/test_config_logs_repositories_postgres.py`: configuration and email-log checks.

### Modify

- `backend/config.py`: replace required Supabase settings with `DATABASE_URL`.
- `backend/requirements.txt`: replace `supabase` with `psycopg[binary,pool]`.
- `backend/repositories/factura_repository.py`: parameterized PostgreSQL queries and transaction.
- `backend/repositories/config_repository.py`: parameterized PostgreSQL queries and audit transaction.
- `backend/repositories/logs_repository.py`: PostgreSQL pagination and count.
- `backend/services/supabase_service.py`: delete after callers move.
- `backend/services/email_service.py`: write logs through `logs_repository`.
- `backend/repositories/factura_async_repository.py`: save causaciones through `factura_repository`.
- `backend/services/factura_service.py`: remove unused asynchronous job API.
- `backend/routers/facturas.py`: remove unused job endpoints.
- `backend/main.py`: open and close database pool with application lifespan.
- `backend/tests/conftest.py`: configure `DATABASE_URL`.
- `.env.example`: document `DATABASE_URL` and remove server Supabase secrets.
- `docker-compose.yml`: add PostgreSQL for local development and remove Redis/worker.
- `README.md`: update database setup and migration commands.

### Delete

- `backend/repositories/job_repository.py`
- `backend/services/job_dispatcher.py`
- `backend/workers/broker.py`
- `backend/workers/tasks.py`
- `backend/workers/__init__.py`
- `backend/tests/test_supabase_service.py`
- `backend/services/supabase_service.py`
- `supabase/007_job_tasks_queue.sql`

---

### Task 1: Capture and prove the real schema

**Files:**
- Create: `database/schema.sql`
- Create: `database/verify.sql`
- Create: `docker-compose.test.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `SOURCE_DATABASE_URL`, supplied locally from Supabase Dashboard and never committed.
- Produces: portable `database/schema.sql` and a local PostgreSQL instance at `postgresql://syncbank:syncbank@localhost:55432/syncbank`.

- [ ] **Step 1: Create the disposable PostgreSQL definition**

```yaml
# docker-compose.test.yml
services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: syncbank
      POSTGRES_USER: syncbank
      POSTGRES_PASSWORD: syncbank
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U syncbank -d syncbank"]
      interval: 2s
      timeout: 2s
      retries: 20
```

- [ ] **Step 2: Export the live public schema**

Run with a direct/session Supabase connection string stored only in the process environment:

```powershell
pg_dump $env:SOURCE_DATABASE_URL --schema=public --schema-only --no-owner --no-privileges --file=database/schema.sql
```

Expected: `database/schema.sql` defines `facturas`, `items_factura`, `causaciones`, `config_cuentas`, `config_cuentas_audit`, and `logs_email`; it must not contain secret values.

- [ ] **Step 3: Remove Supabase-only policy statements from the portable schema**

Run:

```powershell
rg -n "auth\.|authenticated|anon|service_role|ROW LEVEL SECURITY|CREATE POLICY" database/schema.sql
```

Expected: review every match. Remove grants/policies that reference Supabase roles; retain tables, constraints, indexes, functions, and triggers needed by the application.

- [ ] **Step 4: Add deterministic verification queries**

```sql
-- database/verify.sql
select 'facturas' as tabla, count(*) as filas from public.facturas
union all select 'items_factura', count(*) from public.items_factura
union all select 'causaciones', count(*) from public.causaciones
union all select 'config_cuentas', count(*) from public.config_cuentas
union all select 'config_cuentas_audit', count(*) from public.config_cuentas_audit
union all select 'logs_email', count(*) from public.logs_email
order by tabla;

select
  count(*) filter (where cufe is not null and btrim(cufe) <> '') as cufes,
  count(distinct cufe) filter (where cufe is not null and btrim(cufe) <> '') as cufes_unicos,
  coalesce(sum(total::numeric), 0) as total_facturas
from public.facturas;
```

- [ ] **Step 5: Restore the schema into a clean PostgreSQL**

```powershell
docker compose -f docker-compose.test.yml up -d postgres-test
psql "postgresql://syncbank:syncbank@localhost:55432/syncbank" -v ON_ERROR_STOP=1 -f database/schema.sql
psql "postgresql://syncbank:syncbank@localhost:55432/syncbank" -v ON_ERROR_STOP=1 -f database/verify.sql
```

Expected: restore exits `0`; every table returns zero rows; CUFE counts are both zero.

- [ ] **Step 6: Document the commands without credentials**

Add to `README.md`:

```markdown
### PostgreSQL local

`docker compose -f docker-compose.test.yml up -d postgres-test` starts a disposable PostgreSQL on port 55432.
Apply the schema with `psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql`.
Never commit `SOURCE_DATABASE_URL`, dumps containing production data, or database passwords.
```

- [ ] **Step 7: Commit**

```powershell
git add database/schema.sql database/verify.sql docker-compose.test.yml README.md
git commit -m "chore: capture portable PostgreSQL schema"
```

---

### Task 2: Introduce the PostgreSQL pool alongside Supabase

**Files:**
- Create: `backend/repositories/database.py`
- Create: `backend/tests/test_database.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `settings.DATABASE_URL: str`.
- Produces: `open_pool() -> None`, `close_pool() -> None`, `connection() -> Iterator[psycopg.Connection]`, and `transaction() -> Iterator[psycopg.Connection]`.

- [ ] **Step 1: Write the failing settings and pool tests**

```python
# backend/tests/test_database.py
from repositories import database


def test_database_url_is_configured():
    from config import settings

    assert settings.DATABASE_URL.startswith("postgresql://")


def test_pool_is_lazy_before_startup():
    assert database.pool.closed
```

- [ ] **Step 2: Update the test environment and verify failure**

Add to `backend/tests/conftest.py`:

```python
"DATABASE_URL": "postgresql://syncbank:syncbank@localhost:55432/syncbank",
```

Run:

```powershell
Set-Location backend
python -m pytest tests/test_database.py -q
```

Expected: FAIL because `DATABASE_URL` and `repositories.database` do not exist.

- [ ] **Step 3: Add PostgreSQL settings without removing Supabase yet**

In `backend/config.py`, add these fields and retain `SUPABASE_*` until Task 6 so every intermediate commit remains runnable:

```python
DATABASE_URL: str
DB_POOL_MIN_SIZE: int = 1
DB_POOL_MAX_SIZE: int = 5
```

- [ ] **Step 4: Add the PostgreSQL dependency**

In `backend/requirements.txt`, retain `supabase>=2.4.3` temporarily and add:

```text
psycopg[binary,pool]==3.2.10
```

- [ ] **Step 5: Implement the lazy pool**

```python
# backend/repositories/database.py
from contextlib import contextmanager
from collections.abc import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import settings


pool = ConnectionPool(
    conninfo=settings.DATABASE_URL,
    min_size=settings.DB_POOL_MIN_SIZE,
    max_size=settings.DB_POOL_MAX_SIZE,
    kwargs={"row_factory": dict_row},
    open=False,
)


def open_pool() -> None:
    pool.open(wait=True)


def close_pool() -> None:
    pool.close()


@contextmanager
def connection() -> Iterator[Connection]:
    with pool.connection() as conn:
        yield conn


@contextmanager
def transaction() -> Iterator[Connection]:
    with pool.connection() as conn:
        with conn.transaction():
            yield conn
```

- [ ] **Step 6: Connect the pool to FastAPI lifespan**

Replace the startup event in `backend/main.py` with a lifespan that preserves telemetry and scheduler startup:

```python
from contextlib import asynccontextmanager
from repositories.database import close_pool, open_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    init_telemetry()
    start_scheduler()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="Sync-bank API", lifespan=lifespan)
```

- [ ] **Step 7: Run focused tests**

```powershell
python -m pytest tests/test_database.py -q
```

Expected: `2 passed`.

- [ ] **Step 8: Commit**

```powershell
git add backend/config.py backend/requirements.txt backend/repositories/database.py backend/tests/conftest.py backend/tests/test_database.py backend/main.py
git commit -m "feat: add PostgreSQL connection pool"
```

---

### Task 3: Make invoice persistence transactional

**Files:**
- Modify: `backend/repositories/factura_repository.py`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_factura_repository_postgres.py`

**Interfaces:**
- Consumes: `connection()` and `transaction()` from Task 2.
- Produces: existing repository functions with unchanged arguments and dict/list return values; adds `save_causacion(payload: dict) -> None`.

- [ ] **Step 1: Add the integration reset fixture**

```python
# backend/tests/integration/conftest.py
import os
from pathlib import Path

import psycopg
import pytest


DATABASE_URL = os.environ["DATABASE_URL"]
SCHEMA = Path(__file__).parents[3] / "database" / "schema.sql"


@pytest.fixture(scope="session", autouse=True)
def reset_database():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("drop schema if exists public cascade")
        conn.execute("create schema public")
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
    yield
```

- [ ] **Step 2: Write failing atomicity and duplicate tests**

```python
# backend/tests/integration/test_factura_repository_postgres.py
import pytest

from repositories.database import close_pool, open_pool
from repositories.factura_repository import find_factura_by_cufe, save_factura


@pytest.fixture(scope="module", autouse=True)
def db_pool():
    open_pool()
    yield
    close_pool()


def test_save_factura_inserts_invoice_and_items():
    result = save_factura(
        {"cufe": "CUFE-ATOMIC-1", "numero_factura": "FE-1", "estado": "pendiente", "total": "119.00"},
        [{"descripcion": "Servicio", "cantidad": "1", "precio_unitario": "100.00", "total_linea": "100.00"}],
    )
    assert result["duplicado"] is False
    assert find_factura_by_cufe("CUFE-ATOMIC-1")["numero_factura"] == "FE-1"


def test_save_factura_returns_existing_for_duplicate_cufe():
    first = save_factura(
        {"cufe": "CUFE-DUP-1", "numero_factura": "FE-2", "estado": "pendiente", "total": "10.00"},
        [],
    )
    second = save_factura(
        {"cufe": "CUFE-DUP-1", "numero_factura": "FE-3", "estado": "pendiente", "total": "20.00"},
        [],
    )
    assert second == {"factura_id": first["factura_id"], "duplicado": True}
```

- [ ] **Step 3: Run tests and verify they fail against Supabase code**

```powershell
$env:DATABASE_URL='postgresql://syncbank:syncbank@localhost:55432/syncbank'
python -m pytest tests/integration/test_factura_repository_postgres.py -q
```

Expected: FAIL because the repository still imports Supabase.

- [ ] **Step 4: Replace query construction with parameterized SQL**

Implement repository queries using these exact SQL forms:

```python
FIND_BY_CUFE = "select * from facturas where cufe = %s limit 1"
MARK_ESTADO = "update facturas set estado = %s where id = %s"
GET_WITH_ITEMS = """
select f.*, coalesce(jsonb_agg(i.*) filter (where i.id is not null), '[]'::jsonb) as items_factura
from facturas f
left join items_factura i on i.factura_id = f.id
where f.id = %s
group by f.id
"""
```

For inserts, derive allowed columns from explicit tuples in the repository, build only the placeholder list from those trusted names, and pass all values as parameters. Do not interpolate keys received from requests.

- [ ] **Step 5: Implement `save_factura` in one transaction**

The implementation must:

1. open `transaction()`;
2. insert `facturas` with `on conflict (cufe) where cufe is not null and btrim(cufe) <> '' do nothing returning id`;
3. when no ID is returned, select and return the existing ID with `duplicado=True`;
4. insert all items with `executemany` on the same connection;
5. return only after commit.

Use this item insert shape:

```python
conn.executemany(
    """
    insert into items_factura
      (factura_id, descripcion, cantidad, precio_unitario, descuento,
       iva_porcentaje, total_linea, cuenta_contable_alegra,
       centro_costo_alegra, prefill_source, confidence)
    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
    rows,
)
```

- [ ] **Step 6: Implement reads and updates without changing public signatures**

Cover:

- `find_factura_by_cufe`
- `get_successful_causacion`
- `mark_factura_estado`
- `get_facturas_stats`
- `get_facturas_paginated`
- `get_factura_with_items`
- `update_factura_fields`
- `update_item_fields`
- `list_provider_nits` using `select distinct nit_proveedor`
- `list_factura_items_by_nit`
- `save_causacion`

Dynamic update columns must come from per-function allowlists; reject an empty or unknown payload with `ValueError`.

- [ ] **Step 7: Run repository tests**

```powershell
python -m pytest tests/integration/test_factura_repository_postgres.py tests/test_factura_model.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/repositories/factura_repository.py backend/tests/integration
git commit -m "feat: persist invoices transactionally in PostgreSQL"
```

---

### Task 4: Migrate configuration and email-log repositories

**Files:**
- Modify: `backend/repositories/config_repository.py`
- Modify: `backend/repositories/logs_repository.py`
- Modify: `backend/services/email_service.py`
- Create: `backend/tests/integration/test_config_logs_repositories_postgres.py`

**Interfaces:**
- Consumes: `connection()` and `transaction()`.
- Produces: existing config repository signatures; `upsert_email_log(payload: dict) -> None`; existing `list_logs_paginated` result replaced by `(rows: list[dict], count: int)` and adapted in its router.

- [ ] **Step 1: Write failing repository tests**

```python
# backend/tests/integration/test_config_logs_repositories_postgres.py
from repositories.config_repository import get_config_cuenta, save_config_cuenta
from repositories.logs_repository import list_logs_paginated, upsert_email_log


def test_save_config_writes_current_value_and_audit():
    save_config_cuenta("9001", "Proveedor", "5105", confianza=0.8, source="manual")
    row = get_config_cuenta("9001")
    assert row["id_cuenta_alegra"] == "5105"
    assert row["nombre_proveedor"] == "Proveedor"


def test_email_log_upsert_is_idempotent():
    payload = {"mensaje_id": "msg-1", "remitente": "a@example.com", "asunto": "Factura", "estado": "procesado", "attachments_encontrados": 1}
    upsert_email_log(payload)
    upsert_email_log({**payload, "estado": "error"})
    rows, count = list_logs_paginated(page=1, page_size=10)
    assert count == 1
    assert rows[0]["estado"] == "error"
```

- [ ] **Step 2: Run and verify failure**

```powershell
python -m pytest tests/integration/test_config_logs_repositories_postgres.py -q
```

Expected: FAIL because repositories still depend on Supabase and `upsert_email_log` does not exist.

- [ ] **Step 3: Implement configuration SQL**

Use:

```sql
insert into config_cuentas
  (nit_proveedor, nombre_proveedor, id_cuenta_alegra,
   id_centro_costo_alegra, confianza, activo, source)
values (%s, %s, %s, %s, %s, %s, %s)
on conflict (nit_proveedor) do update set
  nombre_proveedor = excluded.nombre_proveedor,
  id_cuenta_alegra = excluded.id_cuenta_alegra,
  id_centro_costo_alegra = excluded.id_centro_costo_alegra,
  confianza = excluded.confianza,
  activo = excluded.activo,
  source = excluded.source
returning *;
```

Insert the audit row in the same `transaction()`. Preserve list/create/update/delete behavior with explicit allowlists.

- [ ] **Step 4: Implement log upsert and pagination**

Use:

```sql
insert into logs_email
  (mensaje_id, remitente, asunto, estado, attachments_encontrados)
values (%s, %s, %s, %s, %s)
on conflict (mensaje_id) do update set
  remitente = excluded.remitente,
  asunto = excluded.asunto,
  estado = excluded.estado,
  attachments_encontrados = excluded.attachments_encontrados
returning *;
```

Fetch page data with `limit %s offset %s` and run a separate `count(*)` using the same optional `estado` filter.

- [ ] **Step 5: Move email logging to the repository**

Replace:

```python
from services.supabase_service import log_email
```

with:

```python
from repositories.logs_repository import upsert_email_log
```

and call `upsert_email_log(email_log)` through the existing executor.

- [ ] **Step 6: Adapt the logs router to the tuple result**

Return exactly the existing API shape:

```python
rows, total = await run_in_executor(
    lambda: list_logs_paginated(page=page, page_size=page_size, estado=estado)
)
return {"data": rows, "count": total, "page": page, "page_size": page_size}
```

- [ ] **Step 7: Run focused tests**

```powershell
python -m pytest tests/integration/test_config_logs_repositories_postgres.py tests/test_provider_mapping_service.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/repositories/config_repository.py backend/repositories/logs_repository.py backend/services/email_service.py backend/routers/logs.py backend/tests/integration/test_config_logs_repositories_postgres.py
git commit -m "feat: migrate configuration and logs to PostgreSQL"
```

---

### Task 5: Remove the unused Redis job path

**Files:**
- Modify: `backend/routers/facturas.py`
- Modify: `backend/services/factura_service.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/observability/metrics.py`
- Modify: `database/schema.sql`
- Modify: `docker-compose.yml`
- Delete: `backend/repositories/job_repository.py`
- Delete: `backend/services/job_dispatcher.py`
- Delete: `backend/workers/broker.py`
- Delete: `backend/workers/tasks.py`
- Delete: `backend/workers/__init__.py`
- Delete: `supabase/007_job_tasks_queue.sql`

**Interfaces:**
- Consumes: the existing synchronous `POST /api/facturas/{factura_id}/causar` path.
- Produces: no asynchronous job endpoint, Redis configuration, job metrics, or worker service.

- [ ] **Step 1: Write the routing regression test**

Add to `backend/tests/test_facturas_router.py`:

```python
def test_async_job_routes_are_not_registered():
    paths = {route.path for route in router.routes}
    assert "/facturas/jobs/{job_id}" not in paths
    assert "/facturas/{factura_id}/causar-async" not in paths
    assert "/facturas/{factura_id}/causar" in paths
```

- [ ] **Step 2: Run and verify failure**

```powershell
python -m pytest tests/test_facturas_router.py::test_async_job_routes_are_not_registered -q
```

Expected: FAIL because both asynchronous routes are still registered.

- [ ] **Step 3: Delete the asynchronous API and service methods**

Remove from `backend/routers/facturas.py`:

- `GET /facturas/jobs/{job_id}`;
- `POST /facturas/{factura_id}/causar-async`.

Remove `enqueue_causar_factura`, `get_job_status`, and imports of job repository/dispatcher from `backend/services/factura_service.py`.

- [ ] **Step 4: Delete worker code and configuration**

Remove `REDIS_URL` and `JOB_QUEUE_NAME` from settings. Remove `dramatiq[redis]` and `redis` from requirements. Remove `backend-worker` and `redis` from Compose plus their `depends_on` entries.

Remove job-only metric declarations and references; retain HTTP and business metrics.

Remove the `job_tasks` table, indexes, and related objects from `database/schema.sql`; the target database must never create this dead queue table.

- [ ] **Step 5: Delete dead tests and files**

Delete the listed worker/job files and any tests that only assert the removed job path. Keep synchronous causation tests.

- [ ] **Step 6: Run regression tests**

```powershell
python -m pytest tests/test_facturas_router.py tests/test_factura_service.py -q
rg -n "dramatiq|REDIS_URL|JOB_QUEUE_NAME|causar-async|job_tasks" backend docker-compose.yml database/schema.sql
```

Expected: tests pass and `rg` returns no matches.

- [ ] **Step 7: Commit**

```powershell
git add backend docker-compose.yml database/schema.sql supabase/007_job_tasks_queue.sql
git commit -m "refactor: remove unused asynchronous job stack"
```

---

### Task 6: Remove Supabase server code and simplify adapters

**Files:**
- Modify: `backend/repositories/factura_async_repository.py`
- Modify: `backend/services/ingestion_service.py`
- Modify: `backend/services/pdf_ingestion_service.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/test_factura_async_repository.py`
- Delete: `backend/services/supabase_service.py`
- Delete: `backend/tests/test_supabase_service.py`

**Interfaces:**
- Consumes: PostgreSQL repository functions from Tasks 3 and 4.
- Produces: existing async repository ports used by `FacturaService` and ingestion; no Supabase imports.

- [ ] **Step 1: Change the causation adapter test first**

Replace its patch target with:

```python
monkeypatch.setattr(
    "repositories.factura_async_repository.save_causacion",
    fake_save_causacion,
)
```

The test continues to assert the exact causation payload reaches the PostgreSQL repository function.

- [ ] **Step 2: Run the test and verify failure**

```powershell
python -m pytest tests/test_factura_async_repository.py -q
```

Expected: FAIL until `save_causacion` is imported from `factura_repository`.

- [ ] **Step 3: Redirect the adapter**

In `factura_async_repository.py`, import `save_causacion` from `repositories.factura_repository`. Preserve the current async port and executor behavior during this plan so service code remains unchanged.

- [ ] **Step 4: Delete Supabase service and test**

Delete both files, remove `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, and `SUPABASE_REQUIRE_SERVICE_KEY` from `backend/config.py`, and remove `supabase>=2.4.3` from `backend/requirements.txt`. Then run:

```powershell
rg -n "supabase_service|from supabase|SUPABASE_SERVICE_KEY|SUPABASE_REQUIRE_SERVICE_KEY" backend
```

Expected: no matches outside historical documentation.

- [ ] **Step 5: Run backend unit tests**

```powershell
python -m pytest tests -q --ignore=tests/integration
```

Expected: all unit tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend
git commit -m "refactor: remove backend Supabase client"
```

---

### Task 7: Migrate production data and verify parity

**Files:**
- Create locally only, never commit: `backups/supabase-pre-cutover.dump`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `SOURCE_DATABASE_URL` and Railway `DATABASE_PUBLIC_URL` during the controlled migration.
- Produces: Railway PostgreSQL containing the source `public` data with verified counts and totals.

- [ ] **Step 1: Add PostgreSQL to local Compose**

Add:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: syncbank
    POSTGRES_USER: syncbank
    POSTGRES_PASSWORD: syncbank
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U syncbank -d syncbank"]
    interval: 5s
    timeout: 3s
    retries: 10
```

Set backend `DATABASE_URL=postgresql://syncbank:syncbank@postgres:5432/syncbank` and add `postgres_data` to volumes.

- [ ] **Step 2: Update environment documentation**

Replace server-side Supabase variables in `.env.example` with:

```text
DATABASE_URL=postgresql://syncbank:syncbank@postgres:5432/syncbank
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=5
```

Leave frontend Supabase variables temporarily; their removal belongs to the frontend/authentication plan.

- [ ] **Step 3: Export source data**

```powershell
pg_dump $env:SOURCE_DATABASE_URL --schema=public --exclude-table=public.job_tasks --data-only --no-owner --no-privileges --format=custom --file=backups/supabase-pre-cutover.dump
psql $env:SOURCE_DATABASE_URL -f database/verify.sql | Tee-Object backups/source-verification.txt
```

Expected: both files exist under ignored `backups/`; no dump is staged by Git.

- [ ] **Step 4: Restore into Railway staging**

```powershell
psql $env:DATABASE_PUBLIC_URL -v ON_ERROR_STOP=1 -f database/schema.sql
pg_restore --dbname=$env:DATABASE_PUBLIC_URL --data-only --no-owner --no-privileges --single-transaction backups/supabase-pre-cutover.dump
psql $env:DATABASE_PUBLIC_URL -f database/verify.sql | Tee-Object backups/target-verification.txt
```

Expected: restore exits `0` and source/target row counts, unique CUFE count, and total sum match exactly.

- [ ] **Step 5: Run staging integration and smoke tests**

```powershell
$env:DATABASE_URL=$env:DATABASE_PUBLIC_URL
Set-Location backend
python -m pytest tests -q
```

Then verify through the deployed staging API:

```powershell
Invoke-RestMethod "$env:STAGING_API_URL/api/facturas/?page=1&page_size=1"
Invoke-RestMethod "$env:STAGING_API_URL/api/facturas/stats"
Invoke-RestMethod "$env:STAGING_API_URL/api/logs/?page=1&page_size=1"
```

Expected: HTTP 200 and non-empty data matching the source when source tables are non-empty.

- [ ] **Step 6: Document the cutover and rollback**

Add to `README.md`:

```markdown
### Cutover PostgreSQL

1. Pause email synchronization and user writes.
2. Create and verify a final Supabase dump.
3. Restore schema and data into an empty Railway PostgreSQL.
4. Compare `database/verify.sql` output on both databases.
5. Point the backend `DATABASE_URL` to Railway and deploy.
6. Run API smoke tests, then resume synchronization.
7. Roll back by restoring the previous backend variables and deployment; never allow writes to both databases simultaneously.
```

- [ ] **Step 7: Commit configuration and documentation only**

```powershell
git status --short backups
git add .env.example docker-compose.yml README.md
git commit -m "docs: add PostgreSQL cutover workflow"
```

Expected: nothing under `backups/` is staged.

---

### Task 8: Final PostgreSQL verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `changelog.md`

**Interfaces:**
- Consumes: completed Tasks 1-7.
- Produces: CI-proven PostgreSQL repository behavior and an operational change record.

- [ ] **Step 1: Add a PostgreSQL service to backend CI**

Under the backend job add:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_DB: syncbank
      POSTGRES_USER: syncbank
      POSTGRES_PASSWORD: syncbank
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U syncbank -d syncbank"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 10
```

Set the backend test environment:

```yaml
DATABASE_URL: postgresql://syncbank:syncbank@localhost:5432/syncbank
```

Remove server-side `SUPABASE_*` variables.

- [ ] **Step 2: Run the complete local verification**

```powershell
docker compose -f docker-compose.test.yml up -d postgres-test
$env:DATABASE_URL='postgresql://syncbank:syncbank@localhost:55432/syncbank'
Set-Location backend
python -m pytest tests -q
ruff check .
black --check .
```

Expected: all commands exit `0`.

- [ ] **Step 3: Verify dependency and reference removal**

```powershell
Set-Location ..
rg -n "from supabase|SUPABASE_SERVICE_KEY|SUPABASE_REQUIRE_SERVICE_KEY|dramatiq|REDIS_URL|JOB_QUEUE_NAME|job_tasks" backend docker-compose.yml .env.example
```

Expected: no matches.

- [ ] **Step 4: Add the changelog entry**

Record:

- PostgreSQL direct access through `psycopg`;
- transactional invoice/item writes;
- schema/data verification method;
- removal of backend Supabase and unused worker stack;
- rollback procedure;
- frontend Supabase cleanup deferred to the approved frontend/authentication plan.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml changelog.md
git commit -m "test: verify PostgreSQL migration in CI"
```

- [ ] **Step 6: Review the complete branch**

```powershell
git status --short
git log --oneline --decorate -10
git diff HEAD~8..HEAD --stat
```

Expected: only pre-existing unrelated user changes remain unstaged; this plan contributes eight focused commits.

---

## Follow-on Plans

After this plan is merged and verified, create and execute two separate plans in this order:

1. `ingestion-pdf-refactor`: modularize IMAP/XML/PDF ingestion, add `documentos_pendientes`, implement page grouping and mandatory review, move OCR into backend, and remove AI Service/Ollama.
2. `production-consolidation`: compile React into FastAPI, implement the single-account secure session, remove frontend Supabase, close CORS, and deploy the two-service Railway topology.

Do not combine either follow-on plan with the PostgreSQL cutover.
