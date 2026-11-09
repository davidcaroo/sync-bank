# ReteFuente duplicada — Plan de corrección y auditoría

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el parser DIAN lea cada retención una sola vez, y saber qué facturas (empezando por el NIT 7474113) quedaron guardadas o causadas con la retención duplicada.

**Architecture:** La corrección va en un solo punto, `DIANParser._extract_retentions` (`backend/services/xml_parser.py:238`). Todos los consumidores (ingesta, PDF, modal, auto-causación) leen de ahí. La auditoría es un script de solo lectura que vuelve a parsear `facturas.xml_raw`, lo compara con las columnas guardadas y, con `--apply`, corrige esas columnas. Alegra no se toca.

**Tech Stack:** Python 3, lxml, psycopg (`repositories.database.connection`), pytest.

**Spec:** Este documento (no hay spec aparte). Evidencia: factura FE260 de JULIO CESAR CHARRIS BLANCO (NIT 7474113, CUFE `53faa0b4…bbef6`). PDF: Total Bruto 14.458.500,00 · IVA 19 % 2.747.115,00 · **Retefuente 3,5 % 506.047,50** · **Total a pagar 16.699.567,50**. Sync-bank muestra ReteFuente 1.012.095 y Total neto 16.193.520.

## Diagnóstico (antes de codificar)

- 1.012.095 = 2 × 506.047,50, exacto.
- `_extract_retentions` usa `//cac:WithholdingTaxTotal/cac:TaxSubtotal` y `//cac:WithholdingTaxTotal/cbc:TaxAmount`. El `//` incluye el `WithholdingTaxTotal` del encabezado **y** el de cada `cac:InvoiceLine`. Este proveedor lo declara en ambos niveles, así que la suma sale doble.
- `_resolve_total` resta ese `withholding_total` doblado cuando `PayableAmount == TaxInclusiveAmount`, por eso el total también queda mal por 506.047,50.
- La auto-causación (`auto_causacion_service.py:90`) no detecta el error, porque el total esperado y el total guardado salen del mismo parse doblado.
- **Impacto contable:** el payload del bill en Alegra (`alegra_client.py:834-853`) **no envía retenciones ni total**, solo categorías con precio, cantidad e IVA. El error afecta los datos de Sync-bank (columnas `rete_fuente` y `total`, modal, validación de auto-causación), no el asiento de Alegra. La Tarea 3 lo comprueba bill por bill, en lugar de darlo por hecho.

## Global Constraints

- Moneda en COP con 2 decimales; compara con tolerancia de 0,01 (igual que `CENT` en `auto_causacion_service.py`).
- Nada de escribir en Alegra. La auditoría solo lee bills con `AlegraClient.get_bill_by_id`.
- Por defecto el script no escribe en la BD; solo `--apply` actualiza `facturas`.
- Sin dependencias nuevas.

## Review Focus

1. **Retención solo en las líneas** (sin nodo en el encabezado): aun así se debe leer una vez, sumando las líneas. Test en la Tarea 2.
2. **Retención solo en el encabezado** (el caso normal de hoy): no debe cambiar. Lo cubren los tests existentes y uno nuevo en la Tarea 2.
3. **Varias líneas, cada una con su retención, más el encabezado:** se usa el encabezado, no encabezado + Σ líneas. Test en la Tarea 2.
4. **AttachedDocument** (sobre DIAN con la factura embebida, como FE260): tras `_unwrap_attached_document` la raíz es `Invoice`, así que `/*/` apunta al nodo correcto. Test en la Tarea 2 (envuelve el XML).
5. **Factura ya causada en Alegra con valores doblados:** la auditoría la reporta con `alegra_bill_id` y el total del bill en Alegra, para que contabilidad decida. Nunca se corrige sola en Alegra. Cubierto en la Tarea 3.

---

### Task 1: Confirmar la hipótesis con el XML real de FE260 (solo lectura)

**Files:** ninguno (verificación).

- [ ] **Step 1: Sacar el XML guardado y contar los nodos de retención**

Run (desde `backend/`, con `.env` apuntando a la BD de producción o a una copia):
```bash
python -c "
from repositories.database import connection
from lxml import etree
from services.xml_parser import DIANParser
p=DIANParser()
with connection() as c:
    r=c.execute(\"select xml_raw, rete_fuente, total, estado from facturas where cufe like '53faa0b4%'\").fetchone()
t=p._unwrap_attached_document(etree.fromstring(r['xml_raw'].encode()))
ns=p.namespaces
print('root', len(t.xpath('/*/cac:WithholdingTaxTotal',namespaces=ns)))
print('lines', len(t.xpath('//cac:InvoiceLine/cac:WithholdingTaxTotal',namespaces=ns)))
print('payable', t.xpath('//cac:LegalMonetaryTotal/cbc:PayableAmount/text()',namespaces=ns))
print('stored', r['rete_fuente'], r['total'], r['estado'])"
```
Esperado: `root 1`, `lines 1`, stored `1012095.00 16193520.00`. Si `lines` sale 0, la hipótesis es falsa: detente y vuelve a diagnosticar con `superpowers:systematic-debugging`.

---

### Task 2: El parser lee cada retención una sola vez

**Files:**
- Modify: `backend/services/xml_parser.py:238-294` (`_extract_retentions`)
- Test: `backend/tests/test_xml_parser.py`

**Interfaces:**
- Produces: `DIANParser._extract_retentions(tree) -> dict` con las mismas claves de hoy (`rete_fuente`, `rete_ica`, `rete_iva`, `withholding_total`). Solo cambia de dónde lee.

- [ ] **Step 1: Escribir los tests que fallan**

Agrega un helper `_withholding_invoice_xml(header: bool, lines: list[float]) -> str`, basado en `_invoice_xml()` con los números de FE260: `LineExtensionAmount` 14458500, `TaxInclusiveAmount` 17205615, `PayableAmount` 17205615, IVA 2747115. Si `header` es verdadero, pone un `cac:WithholdingTaxTotal` a nivel raíz con `TaxAmount` = Σ`lines` y un `TaxSubtotal` con `TaxScheme/cbc:ID` `06`. Pone un `cac:InvoiceLine` por cada valor de `lines`, cada una con su propio `cac:WithholdingTaxTotal` (esquema `06`, ese monto).

```python
def test_retefuente_declared_in_header_and_line_is_counted_once():
    f = parse_xml_dian(_withholding_invoice_xml(header=True, lines=[506047.50]))
    assert f.rete_fuente == 506047.50
    assert f.total == 16699567.50

def test_retefuente_only_in_lines_is_summed_from_lines():
    f = parse_xml_dian(_withholding_invoice_xml(header=False, lines=[300000.0, 206047.50]))
    assert f.rete_fuente == 506047.50
    assert f.total == 16699567.50

def test_header_wins_over_several_line_retentions():
    f = parse_xml_dian(_withholding_invoice_xml(header=True, lines=[300000.0, 206047.50]))
    assert f.rete_fuente == 506047.50

def test_header_and_line_retention_inside_attached_document_counted_once():
    inner = _withholding_invoice_xml(header=True, lines=[506047.50])
    wrapped = (
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
        'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
        "<cac:Attachment><cac:ExternalReference><cbc:Description><![CDATA["
        + inner + "]]></cbc:Description></cac:ExternalReference></cac:Attachment></AttachedDocument>"
    )
    assert parse_xml_dian(wrapped).rete_fuente == 506047.50
```

- [ ] **Step 2: Correrlos para ver que fallan**

Run: `cd backend && pytest tests/test_xml_parser.py -k "retefuente or retention" -v`
Esperado: FAIL en el primero, el tercero y el cuarto (`1012095.0 != 506047.5`, o `806047.5` en el tercero). El segundo puede pasar desde ya.

- [ ] **Step 3: Implementar en `_extract_retentions`**

Lee los `TaxSubtotal` y el `TaxAmount` desde `/*/cac:WithholdingTaxTotal` (nivel raíz). Si no hay ningún nodo raíz, usa `//cac:InvoiceLine/cac:WithholdingTaxTotal` como respaldo. Un solo cambio: elige el prefijo XPath una vez (`base = "/*/cac:WithholdingTaxTotal"` o el de líneas) y reutilízalo en las dos consultas. El resto de la función no cambia.

- [ ] **Step 4: Correr toda la suite**

Run: `cd backend && pytest -q`
Esperado: todo PASS, incluido `test_peaje_*` y los tests de auto-causación.

- [ ] **Step 5: Commit**

```bash
git add backend/services/xml_parser.py backend/tests/test_xml_parser.py
git commit -m "fix: count each DIAN withholding once (header, else lines)"
```

---

### Task 3: Script de auditoría y corrección de datos guardados

**Files:**
- Create: `backend/scripts/audit_retenciones.py`

**Interfaces:**
- Consumes: `parse_xml_dian(xml) -> FacturaDIAN` (ya corregido en la Tarea 2), `repositories.database.connection()`, `factura_repository.get_successful_causacion(factura_id) -> dict | None`, `AlegraClient.get_bill_by_id(client, bill_id) -> dict | None`.
- Produces: CLI `python scripts/audit_retenciones.py [--nit 7474113] [--apply]`.

- [ ] **Step 1: Escribir el script**

`find_mismatches(rows: list[dict]) -> list[dict]` es pura (testeable). Para cada fila con `xml_raw`, re-parsea y devuelve las que tengan `rete_fuente`, `rete_ica`, `rete_iva` o `total` distinto del guardado en más de 0,01, con los valores viejo y nuevo. `main()`:
1. `select id, cufe, numero_factura, nit_proveedor, rete_fuente, rete_ica, rete_iva, total, estado, xml_raw from facturas` (filtra con `where nit_proveedor = %s` si viene `--nit`).
2. Imprime una tabla: número, NIT, estado, rete_fuente guardada → nueva, total guardado → nuevo, `alegra_bill_id` (de `get_successful_causacion`).
3. Para las que tienen `alegra_bill_id`: `get_bill_by_id` e imprime `total`, `balance` y cualquier retención del bill. Así contabilidad ve si el asiento en Alegra quedó bien (según el diagnóstico, debería) o si el pago de anticipos (commit `b2f3d05`) se aplicó sobre un saldo distinto.
4. Con `--apply`: `update facturas set rete_fuente, rete_ica, rete_iva, total, updated_at = now() where id = %s` para cada diferencia, dentro de `transaction()`.

- [ ] **Step 2: Un test para `find_mismatches`**

En `backend/tests/test_audit_retenciones.py`: una fila con `xml_raw = _withholding_invoice_xml(header=True, lines=[506047.50])` (importa el helper de `test_xml_parser`), guardada con `rete_fuente=1012095`, `total=16193520`. Debe devolver un mismatch con `rete_fuente` nueva `506047.50` y `total` nuevo `16699567.50`. Una segunda fila ya correcta no debe aparecer.

Run: `cd backend && pytest tests/test_audit_retenciones.py -v` → PASS

- [ ] **Step 3: Correr en seco, primero para el proveedor y luego para todos**

Run: `cd backend && python scripts/audit_retenciones.py --nit 7474113`
Esperado: FE260 aparece (1012095 → 506047.50). Anota cualquier otra FE de este NIT y su estado y bill.

Run: `cd backend && python scripts/audit_retenciones.py`
Esperado: lista de todos los proveedores afectados. Pasa la salida al usuario y a contabilidad **antes** de `--apply`.

- [ ] **Step 4: Aplicar solo con el OK del usuario**

Run: `cd backend && python scripts/audit_retenciones.py --apply`, luego repite el paso en seco. Esperado: 0 diferencias.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/audit_retenciones.py backend/tests/test_audit_retenciones.py
git commit -m "feat: audit script to re-derive stored withholdings from xml_raw"
```

---

### Task 4: Verificación en la app

- [ ] **Step 1:** Abre FE260 en el modal. Esperado: ReteFuente $506.047,50 (o $506.048 redondeado), Total retenciones igual, Total neto $16.699.567,50. Coincide con el PDF.
- [ ] **Step 2:** Si FE260 sigue `pendiente`, causarla y confirmar en Alegra que el bill sale con subtotal 14.458.500 + IVA 2.747.115. La retefuente la aplica contabilidad o la configuración de Alegra, no este payload.
- [ ] **Step 3:** Actualiza `changelog.md` con una línea sobre la corrección.

---

**Fuera de alcance (anotado, no se hace):** el bill de Alegra no lleva retenciones. Si contabilidad espera que Sync-bank registre la retefuente en Alegra, eso es una funcionalidad aparte.
