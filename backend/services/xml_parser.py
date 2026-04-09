from lxml import etree
from models.factura import FacturaDIAN, FacturaItem
from dateutil import parser
from datetime import datetime
import re


def _normalize_nit(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    raw = str(value).strip()
    if not raw:
        return default
    raw = raw.replace(",", "")
    try:
        return float(raw)
    except Exception:
        return default

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

    def sum_texts(xpath, ns=namespaces):
        values = tree.xpath(xpath, namespaces=ns)
        total = 0.0
        for node in values or []:
            text = getattr(node, "text", None)
            total += _to_float(text)
        return total

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

    subtotal = _to_float(get_text("//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"))
    tax_inclusive = _to_float(get_text("//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount"))
    payable_amount = _to_float(get_text("//cac:LegalMonetaryTotal/cbc:PayableAmount"))
    allowances_total = _to_float(get_text("//cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount"))
    charges_total = _to_float(get_text("//cac:LegalMonetaryTotal/cbc:ChargeTotalAmount"))
    prepaid_amount = _to_float(
        get_text("//cac:LegalMonetaryTotal/cbc:PrepaidAmount")
        or get_text("//cbc:PrepaidAmount")
    )
    rounding_amount = _to_float(
        get_text("//cac:LegalMonetaryTotal/cbc:PayableRoundingAmount")
        or get_text("//cac:LegalMonetaryTotal/cbc:RoundingAmount")
    )

    iva = _to_float(
        get_text("//cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID='01']/cbc:TaxAmount")
    )
    if iva <= 0:
        iva = _to_float(get_text("//cac:TaxTotal/cbc:TaxAmount"))

    rete_fuente = 0.0
    rete_ica = 0.0
    rete_iva = 0.0

    withholding_subtotals = tree.xpath("//cac:WithholdingTaxTotal/cac:TaxSubtotal", namespaces=namespaces)
    for subtotal_node in withholding_subtotals:
        scheme_id = ""
        scheme_name = ""

        scheme_id_nodes = subtotal_node.xpath("cac:TaxCategory/cac:TaxScheme/cbc:ID", namespaces=namespaces)
        if scheme_id_nodes and getattr(scheme_id_nodes[0], "text", None):
            scheme_id = scheme_id_nodes[0].text.strip().upper()

        scheme_name_nodes = subtotal_node.xpath("cac:TaxCategory/cac:TaxScheme/cbc:Name", namespaces=namespaces)
        if scheme_name_nodes and getattr(scheme_name_nodes[0], "text", None):
            scheme_name = scheme_name_nodes[0].text.strip().lower()

        tax_amount_nodes = subtotal_node.xpath("cbc:TaxAmount", namespaces=namespaces)
        amount = _to_float(tax_amount_nodes[0].text if tax_amount_nodes else None)

        if "ica" in scheme_name or scheme_id in {"08", "ICA"}:
            rete_ica += amount
        elif "fuente" in scheme_name or "renta" in scheme_name or scheme_id in {"06", "RETEFUENTE"}:
            rete_fuente += amount
        elif "iva" in scheme_name or scheme_id in {"04", "RETEIVA"}:
            rete_iva += amount

    withholding_total = sum_texts("//cac:WithholdingTaxTotal/cbc:TaxAmount")
    if withholding_total <= 0:
        withholding_total = rete_fuente + rete_ica + rete_iva

    if rete_fuente + rete_ica + rete_iva <= 0 and withholding_total > 0:
        # Keep track of real payable even if supplier does not classify retention types.
        rete_fuente = withholding_total

    gross_for_formula = tax_inclusive if tax_inclusive > 0 else (subtotal + iva)
    net_from_components = gross_for_formula + charges_total - allowances_total - prepaid_amount - withholding_total + rounding_amount

    if payable_amount > 0:
        total = payable_amount
        # Some providers send PayableAmount as gross and put retentions only in WithholdingTaxTotal.
        if withholding_total > 0 and tax_inclusive > 0 and abs(payable_amount - tax_inclusive) < 0.01:
            total = net_from_components
    else:
        total = net_from_components

    if total <= 0:
        total = gross_for_formula

    def get_line_text(node, xpath, ns=namespaces, default="0"):
        res = node.xpath(xpath, namespaces=ns)
        return res[0].text if res and res[0].text else default

    items = []
    lines = tree.xpath("//cac:InvoiceLine", namespaces=namespaces)
    for line in lines:
        descripcion = get_line_text(line, "cac:Item/cbc:Description", default="Articulo sin descripcion")
        cantidad = _to_float(get_line_text(line, "cbc:InvoicedQuantity", default="1"), default=1.0)
        precio = _to_float(get_line_text(line, "cac:Price/cbc:PriceAmount", default="0"))
        total_linea = _to_float(get_line_text(line, "cbc:LineExtensionAmount", default="0"))
        descuento = 0.0
        allowance_nodes = line.xpath(
            "cac:AllowanceCharge[cbc:ChargeIndicator='false']/cbc:Amount",
            namespaces=namespaces,
        )
        for node in allowance_nodes:
            descuento += _to_float(getattr(node, "text", None))

        iva_porcentaje = _to_float(
            get_line_text(
                line,
                "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
                default="19",
            ),
            default=19.0,
        )
        
        items.append(FacturaItem(
            descripcion=descripcion,
            cantidad=cantidad,
            precio_unitario=precio,
            descuento=descuento,
            iva_porcentaje=iva_porcentaje,
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
        rete_fuente=rete_fuente,
        rete_ica=rete_ica,
        rete_iva=rete_iva,
        total=total,
        xml_raw=xml_content,
        items=items
    )
