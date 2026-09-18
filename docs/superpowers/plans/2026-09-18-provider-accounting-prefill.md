# Provider Accounting Prefill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefill one Alegra account and at most one cost center for every incoming invoice, while allowing explicitly authorized providers such as DEVISAB to be caused automatically from validated IMAP XML.

**Architecture:** Reuse `config_cuentas` as the single provider-rule table and add one opt-in `auto_causar` flag. Treat `(id_cuenta_alegra, id_centro_costo_alegra)` as one invoice-level mapping, copy it to all invoice items, and learn only from successfully caused invoices whose items agree on that pair. A focused autocausation service accepts only validated XML created by IMAP, while every other invoice keeps the existing human review flow.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, PostgreSQL 16, psycopg 3, pytest, React 19, Vite 8, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-18-provider-accounting-prefill-design.md`

## Global Constraints

- Do not add AI, a rules engine, an ORM, a queue, or new database tables.
- One invoice resolves to one account and zero or one cost center.
- A manual rule always wins and must never be overwritten by learning.
- Learn only from successful causations, never from pending, failed, or merely prefilled invoices.
- Preserve manual review and the explicit **Causar en Alegra** action for every
  provider without an active manual autocausation rule.
- Autocausation is opt-in, false by default, XML-only, IMAP-only, and cannot be
  enabled by historical learning.
- Autocausation requires both account and cost center.
- Missing line tax data means IVA 0 %, never the current 19 % default.
- Send the exact XML item description to Alegra category `observations`.
- Preserve existing API response shapes except for additive mapping metadata.
- Keep XML, PDF, upload, and IMAP behavior consistent.
- Account is required to cause; cost center remains optional.
- Do not modify unrelated frontend redesign work.
- Every task ends with focused verification and a dedicated commit.

---

## File Map

### Create

- `backend/services/provider_mapping/normalization.py`: shared NIT normalization.
- `backend/services/auto_causacion_service.py`: eligibility checks and controlled automatic causation.
- `frontend/tests/configuracion-mapping.test.mjs`: payload and mapping presentation checks.

### Modify

- `backend/repositories/factura_repository.py`: return one confirmed mapping candidate per successfully caused invoice.
- `backend/repositories/config_repository.py`: normalize NIT and protect manual rules from automatic upserts.
- `database/schema.sql`: add `auto_causar` to provider configuration and audit.
- `backend/services/xml_parser.py`: preserve zero-tax lines without inventing IVA 19 %.
- `backend/services/alegra_client.py`: send the XML line description as category observations.
- `backend/services/email_service.py`: invoke autocausation only after a new XML invoice is persisted from IMAP.
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

**Interfaces:**

- Consumes: `parse_xml_dian(xml_content: str) -> FacturaDIAN` and
  `IngestionExtractor.extract_xml_documents_from_attachment(file_name, content)`.
- Produces: `FacturaItem.iva_porcentaje == 0` when XML has no line tax and an
  Alegra category payload whose `observations` contains the XML description.
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

## Task 5: Preserve ZIP, tax, and description fidelity for peaje XML

**Files:**

- Modify: `backend/services/xml_parser.py`
- Modify: `backend/services/alegra_client.py`
- Modify: `backend/tests/test_xml_parser.py`
- Modify: `backend/tests/test_alegra_client.py`
- Modify: `backend/tests/test_ingestion_service.py`

- [ ] **Step 1: Add a sanitized peaje XML regression fixture in the test**

Use a minimal `AttachedDocument` containing an embedded invoice with issuer NIT
`901209021`, CUFE, invoice `FEUU2183418`, one COP 13.900 line, no line tax nodes,
and this description:

```text
Paso por Peaje GAMBOTE por el valor de 13.900 con la placa SMN255, el dia 14-09-26 09:12. UT PEAJES NACIONALES NIT:901533793
```

Do not commit the user's original XML or PDF.

- [ ] **Step 2: Assert the parser does not invent IVA**

```python
factura = parse_xml_dian(PEAJE_ATTACHED_DOCUMENT_XML)

assert factura.nit_proveedor == "901209021"
assert factura.numero_factura == "FEUU2183418"
assert factura.subtotal == 13900
assert factura.iva == 0
assert factura.total == 13900
assert factura.items[0].iva_porcentaje == 0
assert factura.items[0].descripcion == PEAJE_DESCRIPTION
```

- [ ] **Step 3: Run the parser test and verify failure**

Run:

```powershell
cd backend
pytest -q tests/test_xml_parser.py -k peaje
```

Expected: FAIL because `_extract_items` currently defaults a missing percentage
to 19.

- [ ] **Step 4: Change the missing percentage default to zero**

In `_extract_items`:

```python
iva_porcentaje = _to_float(
    self._get_line_text(
        line,
        "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
        default="0",
    ),
    default=0.0,
)
```

- [ ] **Step 5: Add a ZIP regression test**

Build an in-memory ZIP containing the sanitized XML and a dummy PDF. Assert the
extractor returns exactly the XML document, reports no error, and ignores the PDF.

```python
result = service.extract_xml_documents_from_attachment("peaje.zip", zip_bytes)
assert [doc.entry_name for doc in result["documents"]] == [
    "peaje.zip/factura.xml"
]
assert result["errors"] == []
```

- [ ] **Step 6: Add the description to the Alegra category payload**

```python
categoria = {
    "id": categoria_id,
    "price": item.precio_unitario,
    "quantity": item.cantidad,
    "observations": (item.descripcion or "")[:500],
}
```

Keep the existing general bill observations. Do not send a tax entry when
`iva_porcentaje == 0`.

- [ ] **Step 7: Verify the outbound payload**

Add a mocked HTTP test asserting:

```python
category = posted_payload["purchases"]["categories"][0]
assert category["observations"] == PEAJE_DESCRIPTION
assert "tax" not in category
```

- [ ] **Step 8: Run focused tests**

Run:

```powershell
cd backend
pytest -q tests/test_xml_parser.py tests/test_alegra_client.py tests/test_ingestion_service.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add backend/services/xml_parser.py backend/services/alegra_client.py backend/tests/test_xml_parser.py backend/tests/test_alegra_client.py backend/tests/test_ingestion_service.py
git commit -m "fix: preserve peaje tax and description from XML"
```

---

## Task 6: Add guarded opt-in autocausation from IMAP XML

**Files:**

- Modify: `database/schema.sql`
- Modify: `backend/repositories/config_repository.py`
- Create: `backend/services/auto_causacion_service.py`
- Modify: `backend/services/email_service.py`
- Create: `backend/tests/test_auto_causacion_service.py`
- Modify: `backend/tests/integration/test_config_logs_repositories_postgres.py`

**Interfaces:**

- Consumes: `get_config_cuenta(nit: str) -> dict | None`,
  `get_factura_with_items(factura_id: str) -> dict | None`, and
  `FacturaService.causar_factura(factura_id: str, overrides_map: dict | None)`.
- Produces: `evaluate_auto_causacion(factura, config) -> AutoCausacionDecision`
  and `AutoCausacionService.try_cause_from_imap_xml(factura_id) -> dict`.

- [ ] **Step 1: Add the opt-in flag to the canonical schema**

```sql
alter table public.config_cuentas
    add column if not exists auto_causar boolean not null default false;

alter table public.config_cuentas_audit
    add column if not exists auto_causar boolean not null default false;
```

Include the column in fresh `create table` definitions and repository allowlists.
Automatic mappings always save `auto_causar = false`.

- [ ] **Step 2: Define the eligibility result and pure guard**

In `auto_causacion_service.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoCausacionDecision:
    eligible: bool
    reason: str
```

Step 4 defines `evaluate_auto_causacion(factura: dict, config: dict | None)`.
Return `eligible=True` only when the config is active, manual, opt-in, matches the
normalized issuer NIT, has account and center, and the invoice has real CUFE,
number, COP currency, positive total, non-empty items, consistent line/subtotal
and invoice totals within COP 0.01.

- [ ] **Step 3: Write table-driven failing guard tests**

Cover each denial independently:

```python
@pytest.mark.parametrize(
    "change,reason",
    [
        ({"cufe": "SIN-CUFE"}, "missing_cufe"),
        ({"moneda": "USD"}, "unsupported_currency"),
        ({"total": 0}, "invalid_total"),
    ],
)
def test_auto_causacion_rejects_invalid_invoice(change, reason):
    factura = {**VALID_FACTURA, **change}
    assert evaluate_auto_causacion(factura, VALID_CONFIG).reason == reason
```

Also reject inactive, historical, non-opt-in, accountless, centerless, NIT-mismatch,
empty-item, and total-mismatch configurations.

- [ ] **Step 4: Implement the minimal guard**

Use `Decimal(str(value))` for comparisons. Do not add scoring or retries:

```python
from decimal import Decimal

from services.provider_mapping.normalization import normalize_nit


CENT = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def evaluate_auto_causacion(
    factura: dict, config: dict | None
) -> AutoCausacionDecision:
    if not config or not config.get("activo"):
        return AutoCausacionDecision(False, "inactive_rule")
    if config.get("source") != "manual" or not config.get("auto_causar"):
        return AutoCausacionDecision(False, "not_authorized")
    if not config.get("id_cuenta_alegra"):
        return AutoCausacionDecision(False, "missing_account")
    if not config.get("id_centro_costo_alegra"):
        return AutoCausacionDecision(False, "missing_cost_center")
    if normalize_nit(factura.get("nit_proveedor")) != normalize_nit(
        config.get("nit_proveedor")
    ):
        return AutoCausacionDecision(False, "nit_mismatch")
    if not factura.get("xml_raw"):
        return AutoCausacionDecision(False, "not_xml")
    if factura.get("cufe") in {None, "", "SIN-CUFE"}:
        return AutoCausacionDecision(False, "missing_cufe")
    if factura.get("numero_factura") in {None, "", "SIN-NUMERO"}:
        return AutoCausacionDecision(False, "missing_number")
    if str(factura.get("moneda") or "").upper() != "COP":
        return AutoCausacionDecision(False, "unsupported_currency")

    items = factura.get("items_factura") or []
    if not items:
        return AutoCausacionDecision(False, "missing_items")
    if _money(factura.get("total")) <= 0:
        return AutoCausacionDecision(False, "invalid_total")
    if abs(sum((_money(item.get("total_linea")) for item in items), Decimal(0))
           - _money(factura.get("subtotal"))) > CENT:
        return AutoCausacionDecision(False, "line_total_mismatch")

    expected_total = (
        _money(factura.get("subtotal"))
        + _money(factura.get("iva"))
        - _money(factura.get("rete_fuente"))
        - _money(factura.get("rete_ica"))
        - _money(factura.get("rete_iva"))
    )
    if abs(expected_total - _money(factura.get("total"))) > CENT:
        return AutoCausacionDecision(False, "invoice_total_mismatch")
    return AutoCausacionDecision(True, "authorized")
```

- [ ] **Step 5: Add the controlled service method**

```python
class AutoCausacionService:
    async def try_cause_from_imap_xml(self, factura_id: str) -> dict:
        factura = await self._factura_repository.get_factura_with_items(factura_id)
        config = await self._config_repository.get_config_cuenta(
            factura.get("nit_proveedor")
        )
        decision = evaluate_auto_causacion(factura, config)
        if not decision.eligible:
            return {"status": "pending", "reason": decision.reason}
        try:
            response = await self._factura_service.causar_factura(factura_id)
            return {"status": "caused", "alegra": response}
        except Exception as exc:
            self._logger.exception(
                "auto_causacion_failed", extra={"factura_id": factura_id}
            )
            await self._factura_repository.update_factura_fields(
                factura_id, {"estado": "pendiente"}
            )
            return {"status": "pending", "reason": "alegra_error"}
```

Log the exception without returning secrets or XML. Reuse existing causation
idempotency; do not implement another retry loop.

- [ ] **Step 6: Invoke it only from the IMAP XML path**

After `process_xml_document` returns `status == "created"` and a `factura_id`,
call `try_cause_from_imap_xml`. Never call it from PDF processing, preview, manual
upload, or historical recomputation.

Extend the email summary with `auto_caused` and `auto_pending`. A rejected or
failed automatic attempt does not make email processing fail because the invoice
is safely persisted for manual review.

- [ ] **Step 7: Test successful and failed orchestration**

Assert:

```python
assert await service.try_cause_from_imap_xml("f1") == {
    "status": "caused",
    "alegra": {"id": "bill-1"},
}
```

For an Alegra rejection, assert the invoice is returned to `pendiente`. For an
ineligible rule, assert `causar_factura` was never called.

- [ ] **Step 8: Run focused tests**

Run:

```powershell
cd backend
pytest -q tests/test_auto_causacion_service.py tests/test_ingestion_service.py tests/test_factura_service.py tests/integration/test_config_logs_repositories_postgres.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add database/schema.sql backend/repositories/config_repository.py backend/services/auto_causacion_service.py backend/services/email_service.py backend/tests
git commit -m "feat: auto-cause authorized IMAP XML invoices"
```

---

## Task 7: Make provider-rule configuration valid and usable

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
    auto_causar: bool = False
    activo: bool = True


class ConfigCuentaUpdate(BaseModel):
    nit_proveedor: str | None = None
    nombre_proveedor: str | None = None
    id_cuenta_alegra: str | None = None
    id_centro_costo_alegra: str | None = None
    auto_causar: bool | None = None
    activo: bool | None = None
```

Set `source="manual"` and `confianza=1` server-side. Convert repository
`ValueError` to HTTP 422 or 409 instead of returning 500.

Reject `auto_causar=true` unless both account and center are present. When an
update changes NIT, account, or center without explicitly re-sending
`auto_causar=true`, persist `auto_causar=false` server-side; do not rely only on
the browser reset.

- [ ] **Step 2: Replace unsupported frontend fields**

Change `emptyForm` to:

```javascript
const emptyForm = {
  nit_proveedor: '',
  nombre_proveedor: '',
  id_cuenta_alegra: '',
  id_centro_costo_alegra: '',
  auto_causar: false,
  activo: true,
}
```

Delete `nombre_cuenta`, `id_retefuente`, `id_reteica`, and `id_reteiva` from the
submitted payload. Account names are derived from the Alegra catalog, not stored
as an unsupported field.

Show the autocausation checkbox only after both account and center are selected.
Its copy must state: “Sólo XML recibido por correo. Si una validación falla, la
factura quedará pendiente”. Changing NIT, account, or center resets the checkbox
to false.

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
  auto_causar: true,
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

## Task 8: Make human review explicit and retain corrections

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

Verify the browser only calls `causarFactura` from the existing button handler.
The server-side IMAP exception is covered independently by Task 6. Account must
be present for every item; center may be empty for manual causation. Preserve the
loading state so the button cannot submit twice.

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

## Task 9: End-to-end verification and Railway release

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
4. Ingest the sanitized peaje ZIP through the IMAP handler with autocausation off;
   verify it stays pending with description and IVA 0 %.
5. Enable autocausation for the DEVISAB test rule and repeat with a mocked Alegra
   client; verify exactly one bill attempt occurs and uses the configured account,
   center, COP 13.900, IVA 0 %, and the XML description.
6. Force an Alegra rejection; verify the invoice remains pending and visible.

- [ ] **Step 4: Update operator documentation**

Replace stale README claims about AI/Supabase and document:

- how to create a provider rule;
- that center is optional and singular;
- that historical learning uses successful causations;
- that causation requires operator confirmation except for a manual XML-only
  autocausation rule;
- how to disable autocausation immediately from the provider rule.

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
- [ ] PDF, carga manual, historial y proveedores sin opt-in nunca autocausan.
- [ ] Only IMAP XML with an active manual opt-in rule can autocause.
- [ ] Missing XML tax data produces IVA 0 %, not 19 %.
- [ ] The exact XML item description reaches the Alegra category observation.
- [ ] A rejected autocausation returns the invoice to `pendiente`.
- [ ] Backend tests, frontend tests, lint, and production build pass.
- [ ] Railway smoke checks pass without causing a real invoice.
