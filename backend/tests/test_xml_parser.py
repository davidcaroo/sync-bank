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
