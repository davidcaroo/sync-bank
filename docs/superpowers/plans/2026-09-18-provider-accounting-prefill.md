# Provider Accounting Prefill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefill one Alegra account and at most one cost center for every incoming invoice using an approved provider rule or confirmed historical causations, while keeping causation explicitly manual.

**Architecture:** Reuse `config_cuentas` as the single provider-rule table. Treat `(id_cuenta_alegra, id_centro_costo_alegra)` as one invoice-level mapping, copy it to all invoice items for Alegra compatibility, and learn only from successfully caused invoices whose items agree on that pair. Keep manual rules authoritative and expose the existing rule through the configuration and invoice-review screens.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, PostgreSQL 16, psycopg 3, pytest, React 19, Vite 8, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-18-provider-accounting-prefill-design.md`

## Global Constraints

- Do not add AI, a rules engine, an ORM, a queue, or new database tables.
- One invoice resolves to one account and zero or one cost center.
- A manual rule always wins and must never be overwritten by learning.
- Learn only from successful causations, never from pending, failed, or merely prefilled invoices.
- Preserve manual review and the explicit **Causar en Alegra** action.
- Preserve existing API response shapes except for additive mapping metadata.
- Keep XML, PDF, upload, and IMAP behavior consistent.
- Account is required to cause; cost center remains optional.
- Do not modify unrelated frontend redesign work.
- Every task ends with focused verification and a dedicated commit.

---

## File Map

### Create

- `backend/services/provider_mapping/normalization.py`: shared NIT normalization.
- `frontend/tests/configuracion-mapping.test.mjs`: payload and mapping presentation checks.

### Modify

- `backend/repositories/factura_repository.py`: return one confirmed mapping candidate per successfully caused invoice.
- `backend/repositories/config_repository.py`: normalize NIT and protect manual rules from automatic upserts.
- `backend/services/provider_mapping/extractor.py`: count `(account, cost_center)` pairs per invoice.
- `backend/services/provider_mapping/evaluator.py`: evaluate a dominant mapping pair.
- `backend/services/provider_mapping/persistor.py`: persist account and cost center together.
- `backend/services/provider_mapping_service.py`: return full mappings and preserve existing confidence thresholds.
- `backend/services/ingestion/processor.py`: apply both values to XML items.
- `backend/services/pdf_ingestion_service.py`: apply both values to PDF items.
- `backend/routers/config.py`: validate configuration requests with Pydantic models.
- `backend/services/factura_service.py`: keep overrides as confirmed history and never auto-cause.
- `frontend/src/pages/Configuracion.jsx`: manage provider, account, and cost center fields supported by the backend.
- `frontend/src/components/FacturaModal.jsx`: expose source and confidence during human review.
- `frontend/src/pages/Facturas.jsx`: preserve mapping metadata and correction payloads.
- `backend/tests/test_provider_mapping_service.py`: pair-based learning and manual-rule protection.
- `backend/tests/test_ingestion_service.py`: XML account-plus-center prefill.
- `backend/tests/test_pdf_ingestion_service.py`: PDF account-plus-center prefill.
- `backend/tests/test_factura_service.py`: explicit human causation and confirmed override persistence.
- `backend/tests/integration/test_config_logs_repositories_postgres.py`: configuration persistence and learning boundaries.
- `backend/tests/integration/test_factura_repository_postgres.py`: successful-history query behavior.

---

## Task 1: Lock the accounting behavior with failing tests

**Files:**

- Modify: `backend/tests/test_provider_mapping_service.py`
- Modify: `backend/tests/integration/test_factura_repository_postgres.py`
- Modify: `backend/tests/integration/test_config_logs_repositories_postgres.py`

- [ ] **Step 1: Add a service test for an account-center pair**

Replace the account-only dummy result with mapping pairs and assert both fields:

```python
@pytest.mark.asyncio
async def test_provider_mapping_learns_account_and_cost_center_together():
    service = ProviderMappingService()
    service._historical = DummyExtractor(
        Counter({("5105", "12"): 3, ("5105", "15"): 1}),
        4,
    )
    service._persistor = DummyPersistor()

    result = await service.compute_and_save_mapping("900123456")

    assert result["cuenta"] == "5105"
    assert result["centro_costo"] == "12"
    assert result["confidence"] == 0.75
```

- [ ] **Step 2: Add an integration test that history excludes unconfirmed invoices**

Insert one `pendiente`, one failed causation, and three `procesado` invoices. Assert
that only the three successful invoice mappings are returned and each invoice is
one vote regardless of item count.

```python
rows = list_confirmed_provider_mappings("900123456")
assert rows == [
    {"cuenta": "5105", "centro_costo": "12"},
    {"cuenta": "5105", "centro_costo": "12"},
    {"cuenta": "5105", "centro_costo": "12"},
]
```

- [ ] **Step 3: Add an integration test protecting a manual rule**

```python
save_config_cuenta(
    "900123456", "Nitido", "5105", "12", source="manual"
)
save_config_cuenta(
    "900123456", "Nitido", "5195", "15", source="historical"
)

row = get_config_cuenta("900123456")
assert row["id_cuenta_alegra"] == "5105"
assert row["id_centro_costo_alegra"] == "12"
assert row["source"] == "manual"
```

- [ ] **Step 4: Run the focused tests and confirm failure**

Run:

```powershell
cd backend
pytest -q tests/test_provider_mapping_service.py tests/integration/test_factura_repository_postgres.py tests/integration/test_config_logs_repositories_postgres.py
```

Expected: FAIL because the extractor returns account-only counts, the repository
does not filter confirmed history, and automatic upsert can replace manual rules.

- [ ] **Step 5: Commit the failing tests**

```powershell
git add backend/tests/test_provider_mapping_service.py backend/tests/integration/test_factura_repository_postgres.py backend/tests/integration/test_config_logs_repositories_postgres.py
git commit -m "test: define provider accounting mapping behavior"
```

---

## Task 2: Make confirmed invoice history the only learning source

**Files:**

- Modify: `backend/repositories/factura_repository.py`
- Modify: `backend/services/provider_mapping/extractor.py`
- Modify: `backend/services/provider_mapping/evaluator.py`
- Modify: `backend/tests/test_provider_mapping_service.py`

- [ ] **Step 1: Add a repository query for confirmed mappings**

Add `list_confirmed_provider_mappings(nit_proveedor)` using parameterized SQL.
The query must require an `exitoso` causation and aggregate item pairs by invoice:

```sql
select f.id,
       jsonb_agg(
           jsonb_build_object(
               'cuenta', i.cuenta_contable_alegra,
               'centro_costo', i.centro_costo_alegra
           )
       ) as mappings
from facturas f
join items_factura i on i.factura_id = f.id
where f.nit_proveedor = %s
  and exists (
      select 1
      from causaciones c
      where c.factura_id = f.id and c.estado = 'exitoso'
  )
group by f.id
order by f.created_at;
```

Keep `list_factura_items_by_nit` only if another caller still uses it; otherwise
delete it after `rg` confirms there are no references.

- [ ] **Step 2: Count one consistent pair per invoice**

Implement the smallest strict rule in `HistoricalExtractor`:

```python
pairs = {
    (str(item["cuenta"]), str(item["centro_costo"]) if item.get("centro_costo") else None)
    for item in row.get("mappings") or []
    if item.get("cuenta")
}
if len(pairs) == 1:
    counter[next(iter(pairs))] += 1
    total += 1
```

Mixed or empty invoices contribute no vote.

- [ ] **Step 3: Generalize the evaluator without adding a second abstraction**

Keep `evaluate_account_choice` or rename it to `evaluate_mapping_choice`, but
return the selected pair:

```python
top_mapping, top_count = counter.most_common(1)[0]
cuenta, centro_costo = top_mapping
return {
    "cuenta": cuenta,
    "centro_costo": centro_costo,
    "share": top_count / total,
    "total": total,
    "count": top_count,
}
```

Retain `MIN_OCCURRENCES = 3` and `MIN_SHARE = 0.7`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
cd backend
pytest -q tests/test_provider_mapping_service.py tests/integration/test_factura_repository_postgres.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/repositories/factura_repository.py backend/services/provider_mapping backend/tests/test_provider_mapping_service.py backend/tests/integration/test_factura_repository_postgres.py
git commit -m "feat: learn accounting mappings from confirmed invoices"
```

---

## Task 3: Persist complete mappings without overwriting manual rules

**Files:**

- Create: `backend/services/provider_mapping/normalization.py`
- Modify: `backend/repositories/config_repository.py`
- Modify: `backend/services/provider_mapping/persistor.py`
- Modify: `backend/services/provider_mapping_service.py`
- Modify: `backend/services/provider_mapping/extractor.py`
- Modify: `backend/tests/test_provider_mapping_service.py`
- Modify: `backend/tests/integration/test_config_logs_repositories_postgres.py`

- [ ] **Step 1: Add one shared NIT normalizer**

```python
import re


def normalize_nit(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))
```

Use it at configuration lookup/save and provider-history lookup boundaries. Do not
add a class or dependency.

- [ ] **Step 2: Pass the center through the persistor and service result**

Change the persistor contract to include:

```python
async def save_mapping(
    self,
    *,
    nit_proveedor: str,
    nombre_proveedor: str | None,
    cuenta: str,
    centro_costo: str | None,
    share: float,
    source: str,
) -> dict | None:
```

Both `compute_and_save_mapping` and `suggest_mapping_from_history` must return
`centro_costo` next to `cuenta`.

- [ ] **Step 3: Protect manual configuration in PostgreSQL**

Before an automatic upsert, lock and inspect the current row in the same
transaction. If its source is `manual`, return it unchanged:

```python
current = conn.execute(
    "select * from config_cuentas where nit_proveedor = %s for update",
    (nit,),
).fetchone()
if current and current.get("source") == "manual" and source != "manual":
    return current
```

Only append to `config_cuentas_audit` when a value was actually created or
changed.

- [ ] **Step 4: Extend the Alegra fallback by bill, not by category line**

For each historical Alegra bill, read its top-level `costCenter`, accept the bill
only when all expense categories resolve to one account, and add one
`(account, cost_center)` vote. Do not infer multiple centers.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd backend
pytest -q tests/test_provider_mapping_service.py tests/test_alegra_extractor.py tests/integration/test_config_logs_repositories_postgres.py
```

Expected: PASS, including manual-rule protection.

- [ ] **Step 6: Commit**

```powershell
git add backend/services/provider_mapping backend/services/provider_mapping_service.py backend/repositories/config_repository.py backend/tests
git commit -m "feat: persist account and cost center provider rules"
```

---

## Task 4: Apply the same mapping in XML, PDF, upload, and IMAP

**Files:**

- Modify: `backend/services/ingestion/processor.py`
- Modify: `backend/services/pdf_ingestion_service.py`
- Modify: `backend/tests/test_ingestion_service.py`
- Modify: `backend/tests/test_pdf_ingestion_service.py`

- [ ] **Step 1: Add failing XML and PDF tests**

For an active provider configuration:

```python
config = {
    "id_cuenta_alegra": "5105",
    "id_centro_costo_alegra": "12",
    "source": "manual",
    "confianza": 1,
}
```

Assert every preview and persisted item contains:

```python
assert item["cuenta_contable_alegra"] == "5105"
assert item["centro_costo_alegra"] == "12"
assert item["prefill_source"] == "manual"
assert item["confidence"] == 1.0
```

Also test a historical suggestion with a center and an unmapped provider with
both fields `None`.

- [ ] **Step 2: Preserve the actual source value**

When applying configuration, use `config["source"]` when present instead of
always reporting `config`. Keep a safe fallback of `config` for older rows.

- [ ] **Step 3: Apply historical account and center together**

In both ingestors:

```python
cuenta_to_save = historical_hint.get("cuenta")
centro_to_save = historical_hint.get("centro_costo")
```

Do not add different behavior for email: IMAP already enters through these
ingestion services.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
cd backend
pytest -q tests/test_ingestion_service.py tests/test_pdf_ingestion_service.py tests/test_ingestion_adapters.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/services/ingestion/processor.py backend/services/pdf_ingestion_service.py backend/tests/test_ingestion_service.py backend/tests/test_pdf_ingestion_service.py
git commit -m "feat: prefill account and cost center during ingestion"
```

---

## Task 5: Make provider-rule configuration valid and usable

**Files:**

- Modify: `backend/routers/config.py`
- Modify: `backend/repositories/config_repository.py`
- Modify: `frontend/src/pages/Configuracion.jsx`
- Create: `frontend/tests/configuracion-mapping.test.mjs`
- Modify: `backend/tests/test_facturas_router.py`

- [ ] **Step 1: Add typed request models in the existing router**

Do not create a schemas package for two payloads. Define them next to the routes:

```python
class ConfigCuentaCreate(BaseModel):
    nit_proveedor: str = Field(min_length=3)
    nombre_proveedor: str | None = None
    id_cuenta_alegra: str = Field(min_length=1)
    id_centro_costo_alegra: str | None = None
    activo: bool = True


class ConfigCuentaUpdate(BaseModel):
    nit_proveedor: str | None = None
    nombre_proveedor: str | None = None
    id_cuenta_alegra: str | None = None
    id_centro_costo_alegra: str | None = None
    activo: bool | None = None
```

Set `source="manual"` and `confianza=1` server-side. Convert repository
`ValueError` to HTTP 422 or 409 instead of returning 500.

- [ ] **Step 2: Replace unsupported frontend fields**

Change `emptyForm` to:

```javascript
const emptyForm = {
  nit_proveedor: '',
  nombre_proveedor: '',
  id_cuenta_alegra: '',
  id_centro_costo_alegra: '',
  activo: true,
}
```

Delete `nombre_cuenta`, `id_retefuente`, `id_reteica`, and `id_reteiva` from the
submitted payload. Account names are derived from the Alegra catalog, not stored
as an unsupported field.

- [ ] **Step 3: Add the cost-center selector**

Use the already loaded `catalogo.cost_centers` array. Include an explicit
“Sin centro de costo” option. Display account, center, source, and active state in
the saved-rules table.

- [ ] **Step 4: Add a small frontend contract test**

Extract only a pure payload helper if needed and verify:

```javascript
assert.deepEqual(buildConfigPayload(form), {
  nit_proveedor: '900123456',
  nombre_proveedor: 'Nitido Car Wash',
  id_cuenta_alegra: '5105',
  id_centro_costo_alegra: '12',
  activo: true,
})
```

Do not add a browser-testing dependency.

- [ ] **Step 5: Run backend and frontend checks**

Run:

```powershell
cd backend
pytest -q tests/test_facturas_router.py tests/integration/test_config_logs_repositories_postgres.py
cd ../frontend
npm test
npm run lint
npm run build
```

Expected: all commands PASS and Vite produces `dist`.

- [ ] **Step 6: Commit**

```powershell
git add backend/routers/config.py backend/repositories/config_repository.py frontend/src/pages/Configuracion.jsx frontend/tests/configuracion-mapping.test.mjs backend/tests
git commit -m "feat: manage provider account and cost center rules"
```

---

## Task 6: Make human review explicit and retain corrections

**Files:**

- Modify: `frontend/src/components/FacturaModal.jsx`
- Modify: `frontend/src/pages/Facturas.jsx`
- Modify: `backend/services/factura_service.py`
- Modify: `backend/tests/test_factura_service.py`

- [ ] **Step 1: Add a causation service regression test**

Assert that a manual override is persisted before sending to Alegra and that no
call to `crear_bill` occurs merely by loading or ingesting a factura.

```python
await service.causar_factura(
    factura_id,
    {
        item_id: {
            "cuenta_contable_alegra": "5105",
            "centro_costo_alegra": "12",
        }
    },
)
repository.update_item_fields.assert_awaited_with(
    item_id,
    {
        "cuenta_contable_alegra": "5105",
        "centro_costo_alegra": "12",
    },
)
```

- [ ] **Step 2: Show classification provenance in the modal**

Replace the generic auto-prefill message with concise copy based on
`prefill_source`:

```text
Clasificación sugerida por regla manual. Revisa cuenta y centro antes de causar.
```

or:

```text
Clasificación sugerida por historial (75 %). Revisa antes de causar.
```

Keep the selectors editable. Do not add a second confirmation dialog.

- [ ] **Step 3: Keep the explicit cause boundary**

Verify `causarFactura` is only called from the existing button handler. Account
must be present for every item; center may be empty. Preserve the loading state so
the button cannot submit twice.

- [ ] **Step 4: Run focused checks**

Run:

```powershell
cd backend
pytest -q tests/test_factura_service.py tests/test_facturas_router.py
cd ../frontend
npm test
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/services/factura_service.py backend/tests/test_factura_service.py frontend/src/components/FacturaModal.jsx frontend/src/pages/Facturas.jsx
git commit -m "feat: clarify accounting review before causation"
```

---

## Task 7: End-to-end verification and Railway release

**Files:**

- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-09-18-provider-accounting-prefill.md`

- [ ] **Step 1: Run the complete backend suite**

Run:

```powershell
cd backend
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run complete frontend verification**

Run:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Expected: tests and lint PASS; production build succeeds.

- [ ] **Step 3: Perform three local acceptance scenarios**

1. Create a Nitido rule with account and center, ingest a sample, verify both are
   prefilled, and stop before pressing cause.
2. Create a Coordinadora rule with one account and one center, ingest a sample,
   verify every item receives the same pair, then cause only after review.
3. Ingest an unknown provider, verify no invented mapping appears and causation is
   blocked until the account is selected.

- [ ] **Step 4: Update operator documentation**

Replace stale README claims about AI/Supabase and document:

- how to create a provider rule;
- that center is optional and singular;
- that historical learning uses successful causations;
- that causation always requires operator confirmation.

- [ ] **Step 5: Commit the documentation**

```powershell
git add README.md docs/superpowers/plans/2026-09-18-provider-accounting-prefill.md
git commit -m "docs: explain provider accounting prefill workflow"
```

- [ ] **Step 6: Deploy the worktree branch to Railway**

Deploy using the existing Railway project and service configuration. Do not alter
database credentials or create another service.

- [ ] **Step 7: Run production smoke checks**

Verify:

```text
GET /healthz                              -> 200
GET /api/config/                         -> 200 authenticated
GET /api/config/alegra/catalogo          -> 200 authenticated
GET /api/facturas?page=1&page_size=10    -> 200 authenticated
```

Then create or edit one non-destructive provider rule and confirm that a pending
invoice preview displays both values. Do not cause a real invoice as a smoke test
unless accounting explicitly selects it.

- [ ] **Step 8: Record verification evidence**

Check every completed box in this plan and append the exact test totals, build
result, Railway deployment identifier, and smoke-check results under this task.

- [ ] **Step 9: Final commit if the plan gained verification notes**

```powershell
git add docs/superpowers/plans/2026-09-18-provider-accounting-prefill.md
git commit -m "docs: record accounting prefill verification"
```

---

## Completion Checklist

- [ ] No new database table or AI dependency exists.
- [ ] Manual rules cannot be overwritten automatically.
- [ ] Historical learning uses only successful causations.
- [ ] History learns an account-center pair with one vote per invoice.
- [ ] XML, PDF, upload, and IMAP apply identical mappings.
- [ ] Nitido and Coordinadora each resolve to one account and one center.
- [ ] Unknown or ambiguous providers remain for manual review.
- [ ] The operator can correct classifications before causing.
- [ ] No ingestion path automatically causes an invoice.
- [ ] Backend tests, frontend tests, lint, and production build pass.
- [ ] Railway smoke checks pass without causing a real invoice.

