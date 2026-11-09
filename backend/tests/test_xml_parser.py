from services.xml_parser import DIANParser, parse_xml_dian


def _invoice_xml() -> str:
    return """
<Invoice xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UUID>CUFE-ABC</cbc:UUID>
  <cbc:ID>FAC-1</cbc:ID>
  <cbc:IssueDate>2026-04-10</cbc:IssueDate>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>900.123.456-7</cbc:CompanyID>
        <cbc:RegistrationName>Proveedor Test SAS</cbc:RegistrationName>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>800123000</cbc:CompanyID>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount>1000</cbc:LineExtensionAmount>
    <cbc:TaxInclusiveAmount>1190</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount>1190</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:TaxTotal>
    <cbc:TaxAmount>190</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>1000</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>Servicio</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount>1000</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>
""".strip()


def test_parse_xml_dian_keeps_compatibility():
    factura = parse_xml_dian(_invoice_xml())

    assert factura.cufe == "CUFE-ABC"
    assert factura.numero_factura == "FAC-1"
    assert factura.nit_proveedor == "9001234567"
    assert factura.total == 1190
    assert len(factura.items) == 1


def test_dian_parser_class_parse_matches_wrapper():
    parser = DIANParser()
    by_class = parser.parse(_invoice_xml())
    by_wrapper = parse_xml_dian(_invoice_xml())

    assert by_class.cufe == by_wrapper.cufe
    assert by_class.numero_factura == by_wrapper.numero_factura
    assert by_class.total == by_wrapper.total


def test_peaje_invoice_keeps_zero_iva_and_literal_description():
    from peaje_fixture import PEAJE_ATTACHED_DOCUMENT_XML, PEAJE_DESCRIPTION

    factura = parse_xml_dian(PEAJE_ATTACHED_DOCUMENT_XML)

    assert factura.nit_proveedor == "901209021"
    assert factura.numero_factura == "FEUU2183418"
    assert factura.subtotal == 13900
    assert factura.iva == 0
    assert factura.total == 13900
    assert factura.items[0].iva_porcentaje == 0
    assert factura.items[0].descripcion == PEAJE_DESCRIPTION


def test_line_without_tax_node_keeps_legacy_rate_when_header_declares_iva():
    # _invoice_xml() has header IVA (190) but no per-line tax node.
    factura = parse_xml_dian(_invoice_xml())

    assert factura.items[0].iva_porcentaje == 19


def test_dian_event_wrapped_as_attached_document_is_not_an_invoice():
    import pytest

    from services.xml_parser import DianEventError, parse_xml_dian

    xml = (
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2"'
        ' xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
        ' xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">'
        "<cac:Attachment><cac:ExternalReference><cbc:Description><![CDATA["
        '<ApplicationResponse xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
        "<cbc:ID>1</cbc:ID></ApplicationResponse>"
        "]]></cbc:Description></cac:ExternalReference></cac:Attachment></AttachedDocument>"
    )

    with pytest.raises(DianEventError):
        parse_xml_dian(xml)


def test_an_invoice_without_receiver_nit_is_not_given_a_placeholder():
    from services.xml_parser import parse_xml_dian

    xml = (
        '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
        "<cbc:ID>F1</cbc:ID><cbc:UUID>CUFE-1</cbc:UUID>"
        "<cbc:IssueDate>2026-09-10</cbc:IssueDate></Invoice>"
    )

    assert not parse_xml_dian(xml).nit_receptor


DECOY_INVOICE = (
    '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
    'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">'
    "<ext:UBLExtensions><ext:UBLExtension><cbc:ID>900320612</cbc:ID>"
    "<cbc:IssueDate>2020-01-01</cbc:IssueDate></ext:UBLExtension></ext:UBLExtensions>"
    "<cbc:ID>T0916011103</cbc:ID><cbc:UUID>CUFE-REAL</cbc:UUID>"
    "<cbc:IssueDate>2026-09-01</cbc:IssueDate></Invoice>"
)


def test_the_invoice_number_is_the_root_id_not_an_id_from_the_extensions():
    from services.xml_parser import parse_xml_dian

    parsed = parse_xml_dian(DECOY_INVOICE)

    assert parsed.numero_factura == "T0916011103"
    assert parsed.cufe == "CUFE-REAL"
    assert parsed.fecha_emision.date().isoformat() == "2026-09-01"


_NS = (
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
)


def _withholding(amount: float) -> str:
    return (
        "<cac:WithholdingTaxTotal>"
        f"<cbc:TaxAmount>{amount:.2f}</cbc:TaxAmount>"
        "<cac:TaxSubtotal>"
        f"<cbc:TaxAmount>{amount:.2f}</cbc:TaxAmount>"
        "<cac:TaxCategory><cac:TaxScheme><cbc:ID>06</cbc:ID>"
        "<cbc:Name>ReteRenta</cbc:Name></cac:TaxScheme></cac:TaxCategory>"
        "</cac:TaxSubtotal></cac:WithholdingTaxTotal>"
    )


def _withholding_invoice_xml(header: bool, lines: list[float]) -> str:
    """FE260-shaped invoice: retention optionally in the header and on every line."""
    line_base = 14458500 / len(lines)
    invoice_lines = "".join(
        "<cac:InvoiceLine>"
        "<cbc:InvoicedQuantity>1</cbc:InvoicedQuantity>"
        f"<cbc:LineExtensionAmount>{line_base:.2f}</cbc:LineExtensionAmount>"
        + _withholding(amount)
        + "<cac:Item><cbc:Description>ARRENDAMIENTO BODEGA M 10</cbc:Description></cac:Item>"
        f"<cac:Price><cbc:PriceAmount>{line_base:.2f}</cbc:PriceAmount></cac:Price>"
        "</cac:InvoiceLine>"
        for amount in lines
    )
    return (
        f"<Invoice {_NS}>"
        "<cbc:UUID>CUFE-FE260</cbc:UUID><cbc:ID>FE260</cbc:ID>"
        "<cbc:IssueDate>2026-11-03</cbc:IssueDate>"
        "<cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>"
        "<cbc:CompanyID>7474113</cbc:CompanyID>"
        "<cbc:RegistrationName>JULIO CESAR CHARRIS BLANCO</cbc:RegistrationName>"
        "</cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>"
        "<cac:TaxTotal><cbc:TaxAmount>2747115.00</cbc:TaxAmount></cac:TaxTotal>"
        + (_withholding(sum(lines)) if header else "")
        + "<cac:LegalMonetaryTotal>"
        "<cbc:LineExtensionAmount>14458500.00</cbc:LineExtensionAmount>"
        "<cbc:TaxInclusiveAmount>17205615.00</cbc:TaxInclusiveAmount>"
        "<cbc:PayableAmount>17205615.00</cbc:PayableAmount>"
        "</cac:LegalMonetaryTotal>"
        + invoice_lines
        + "</Invoice>"
    )


def test_retefuente_declared_in_header_and_line_is_counted_once():
    f = parse_xml_dian(_withholding_invoice_xml(header=True, lines=[506047.50]))
    assert f.rete_fuente == 506047.50
    assert f.total == 16699567.50


def test_retefuente_only_in_lines_is_summed_from_lines():
    f = parse_xml_dian(
        _withholding_invoice_xml(header=False, lines=[300000.0, 206047.50])
    )
    assert f.rete_fuente == 506047.50
    assert f.total == 16699567.50


def test_header_wins_over_several_line_retentions():
    f = parse_xml_dian(
        _withholding_invoice_xml(header=True, lines=[300000.0, 206047.50])
    )
    assert f.rete_fuente == 506047.50


def test_header_and_line_retention_inside_attached_document_counted_once():
    inner = _withholding_invoice_xml(header=True, lines=[506047.50])
    wrapped = (
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
        + _NS
        + "><cac:Attachment><cac:ExternalReference><cbc:Description><![CDATA["
        + inner
        + "]]></cbc:Description></cac:ExternalReference></cac:Attachment></AttachedDocument>"
    )
    assert parse_xml_dian(wrapped).rete_fuente == 506047.50
