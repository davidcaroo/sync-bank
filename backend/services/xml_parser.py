from lxml import etree
from models.factura import FacturaDIAN, FacturaItem
from dateutil import parser
from datetime import datetime
import re


def _normalize_nit(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)

def parse_xml_dian(xml_content: str) -> FacturaDIAN:
    tree = etree.fromstring(xml_content.encode('utf-8'))
    namespaces = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'fe': 'http://www.dian.gov.co/contratos/facturaelectronica/v1',
        'ad': 'urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2'
    }

    # Unwrapping: If it's an AttachedDocument, the real invoice is inside
    if tree.tag.endswith('AttachedDocument'):
        description_node = tree.xpath(
            "//cac:Attachment/cac:ExternalReference/cbc:Description",
            namespaces=namespaces,
        )
        if description_node:
            try:
                # Pick the first embedded xml payload that actually contains an Invoice.
                embedded_xml = ""
                for node in description_node:
                    candidate = (node.text or "").strip()
                    if "<Invoice" in candidate:
                        embedded_xml = candidate
                        break
                if not embedded_xml and description_node[0].text:
                    embedded_xml = description_node[0].text
                if embedded_xml and '<' in embedded_xml:
                    tree = etree.fromstring(embedded_xml.encode('utf-8'))
            except:
                pass

    def get_text(xpath, ns=namespaces):
        res = tree.xpath(xpath, namespaces=ns)
        if res is not None and len(res) > 0:
            return res[0].text or ""
        return ""

    cufe = get_text("//cbc:UUID") or "SIN-CUFE"
    numero = get_text("//cbc:ID") or "SIN-NUMERO"
    fecha_emision_raw = get_text("//cbc:IssueDate")
    
    # Robust metadata extraction
    nit_proveedor_raw = (
        get_text("//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID") or 
        get_text("//cac:SenderParty/cac:PartyTaxScheme/cbc:CompanyID") or 
        get_text("//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID") or
        ""
    )
    nit_proveedor = _normalize_nit(nit_proveedor_raw) or "999999999"
    
    nombre_proveedor = (
        get_text("//cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name") or 
        get_text("//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName") or
        get_text("//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName") or
        get_text("//cac:PartyName/cbc:Name") or 
        "Proveedor Generico"
    )
    
    nit_receptor_raw = (
        get_text("//cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID") or 
        get_text("//cac:ReceiverParty/cac:PartyTaxScheme/cbc:CompanyID") or 
        get_text("//cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID") or
        ""
    )
    nit_receptor = _normalize_nit(nit_receptor_raw) or "123456789"

    subtotal = float(get_text("//cac:LegalMonetaryTotal/cbc:LineExtensionAmount") or 0)
    total = float(get_text("//cac:LegalMonetaryTotal/cbc:PayableAmount") or 0)
    iva = float(get_text("//cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID='01']/cbc:TaxAmount") or 0)

    def get_line_text(node, xpath, ns=namespaces, default="0"):
        res = node.xpath(xpath, namespaces=ns)
        return res[0].text if res and res[0].text else default

    items = []
    lines = tree.xpath("//cac:InvoiceLine", namespaces=namespaces)
    for line in lines:
        descripcion = get_line_text(line, "cac:Item/cbc:Description", default="Articulo sin descripcion")
        cantidad = float(get_line_text(line, "cbc:InvoicedQuantity", default="1"))
        precio = float(get_line_text(line, "cac:Price/cbc:PriceAmount", default="0"))
        total_linea = float(get_line_text(line, "cbc:LineExtensionAmount", default="0"))
        
        items.append(FacturaItem(
            descripcion=descripcion,
            cantidad=cantidad,
            precio_unitario=precio,
            total_linea=total_linea
        ))

    # Fallback to current time if date is missing
    try:
        dt_emision = parser.parse(fecha_emision_raw) if fecha_emision_raw else datetime.now()
    except:
        dt_emision = datetime.now()

    return FacturaDIAN(
        cufe=cufe,
        numero_factura=numero,
        fecha_emision=dt_emision,
        nit_proveedor=nit_proveedor,
        nombre_proveedor=nombre_proveedor,
        nit_receptor=nit_receptor,
        subtotal=subtotal,
        iva=iva,
        total=total,
        xml_raw=xml_content,
        items=items
    )
