"""Sanitized peaje (DEVISAB) fixtures; the user's original XML/PDF are not stored."""

import io
import zipfile

PEAJE_DESCRIPTION = (
    "Paso por Peaje GAMBOTE por el valor de 13.900 con la placa SMN255, "
    "el dia 14-09-26 09:12. UT PEAJES NACIONALES NIT:901533793"
)

_INVOICE = f"""<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UUID>PEAJE-CUFE-0001</cbc:UUID>
  <cbc:ID>FEUU2183418</cbc:ID>
  <cbc:IssueDate>2026-09-14</cbc:IssueDate>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyTaxScheme>
        <cbc:RegistrationName>DEVISAB S.A.S.</cbc:RegistrationName>
        <cbc:CompanyID>901209021</cbc:CompanyID>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyTaxScheme><cbc:CompanyID>800123000</cbc:CompanyID></cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal><cbc:TaxAmount>0.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount>13900.00</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount>13900.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount>13900.00</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount>13900.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>13900.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Description>{PEAJE_DESCRIPTION}</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount>13900.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""

PEAJE_ATTACHED_DOCUMENT_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:Attachment>
    <cac:ExternalReference>
      <cbc:Description><![CDATA[{_INVOICE}]]></cbc:Description>
    </cac:ExternalReference>
  </cac:Attachment>
</AttachedDocument>"""


def peaje_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("factura.xml", PEAJE_ATTACHED_DOCUMENT_XML)
        archive.writestr("factura.pdf", b"%PDF-1.4 dummy")
    return buffer.getvalue()
