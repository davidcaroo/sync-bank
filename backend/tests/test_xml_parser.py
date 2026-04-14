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