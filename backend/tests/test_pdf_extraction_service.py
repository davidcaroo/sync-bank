from services.pdf_extraction_service import _parse_candidate, _split_page_groups


def test_five_page_invoice_stays_in_one_group():
    pages = [
        "FACTURA ELECTRONICA DE VENTA No. FV-100 NIT 900123456 CUFE: " + "a" * 96,
        "Detalle pagina 2",
        "Detalle pagina 3",
        "Detalle pagina 4",
        "Totales pagina 5 TOTAL $ 119.000,00",
    ]

    assert _split_page_groups(pages) == [(1, 5, "\n\n".join(pages))]


def test_package_splits_when_invoice_identifier_changes():
    pages = [
        "FACTURA ELECTRONICA DE VENTA No. FV-100 NIT 900123456 CUFE: " + "a" * 96,
        "Detalle pagina 2",
        "FACTURA ELECTRONICA DE VENTA No. FV-101 NIT 901987654 CUFE: " + "b" * 96,
    ]

    assert [(start, end) for start, end, _ in _split_page_groups(pages)] == [
        (1, 2),
        (3, 3),
    ]


def test_candidate_extracts_conservative_header_and_totals():
    text = """
    FACTURA ELECTRONICA DE VENTA No. FV-2024-88
    CUFE: abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdef
    NIT: 900.123.456-7
    Fecha de emision: 17/09/2026
    Subtotal: $ 100.000,00
    IVA: $ 19.000,00
    TOTAL A PAGAR: $ 119.000,00
    """

    candidate = _parse_candidate(text, 1, 1)

    assert candidate["numero_factura"] == "FV-2024-88"
    assert candidate["nit_proveedor"] == "9001234567"
    assert candidate["subtotal"] == 100000
    assert candidate["iva"] == 19000
    assert candidate["total"] == 119000
    assert candidate["page_start"] == 1
