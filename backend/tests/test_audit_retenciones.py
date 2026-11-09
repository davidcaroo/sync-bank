from scripts.audit_retenciones import find_mismatches
from test_xml_parser import _withholding_invoice_xml


def _row(**overrides):
    return {
        "id": "f1",
        "numero_factura": "FE260",
        "rete_fuente": 1012095.0,
        "rete_ica": 0,
        "rete_iva": 0,
        "total": 16193520.0,
        "xml_raw": _withholding_invoice_xml(header=True, lines=[506047.50]),
        **overrides,
    }


def test_stored_doubled_retention_is_reported_with_reparsed_values():
    [m] = find_mismatches([_row()])
    assert m["id"] == "f1"
    assert m["new"]["rete_fuente"] == 506047.50
    assert m["new"]["total"] == 16699567.50
    assert m["old"]["rete_fuente"] == 1012095.0


def test_correct_or_xml_less_rows_are_not_reported():
    ok = _row(id="f2", rete_fuente=506047.50, total=16699567.50)
    assert find_mismatches([ok, _row(id="f3", xml_raw=None)]) == []


def test_apply_skips_invoices_already_caused_in_alegra():
    from scripts.audit_retenciones import split_by_causation

    pending, caused = split_by_causation(
        [{"id": "a", "bill_id": None}, {"id": "b", "bill_id": "99"}]
    )
    assert [m["id"] for m in pending] == ["a"]
    assert [m["id"] for m in caused] == ["b"]
