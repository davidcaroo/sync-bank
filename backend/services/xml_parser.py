import re

from dateutil import parser
from dateutil.parser import ParserError
from lxml import etree
from lxml.etree import XMLSyntaxError

from models.factura import FacturaDIAN, FacturaItem
from services.timezone_service import now_bogota


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
    except ValueError:
        return default

class DIANParser:
    def __init__(self) -> None:
        self.namespaces = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "fe": "http://www.dian.gov.co/contratos/facturaelectronica/v1",
            "ad": "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
        }

    def parse(self, xml_content: str) -> FacturaDIAN:
        tree = etree.fromstring(xml_content.encode("utf-8"))
        tree = self._unwrap_attached_document(tree)

        cufe = self._get_text(tree, "//cbc:UUID") or "SIN-CUFE"
        numero = self._get_text(tree, "//cbc:ID") or "SIN-NUMERO"
        fecha_emision_raw = self._get_text(tree, "//cbc:IssueDate")

        nit_proveedor = self._extract_nit_proveedor(tree)
        nombre_proveedor = self._extract_nombre_proveedor(tree)
        nit_receptor = self._extract_nit_receptor(tree)

        totals = self._extract_totals(tree)
        retentions = self._extract_retentions(tree)
        total = self._resolve_total(totals, retentions)
        items = self._extract_items(tree)
        dt_emision = self._parse_issue_date(fecha_emision_raw)

        factura = FacturaDIAN(
            cufe=cufe,
            numero_factura=numero,
            fecha_emision=dt_emision,
            nit_proveedor=nit_proveedor,
            nombre_proveedor=nombre_proveedor,
            nit_receptor=nit_receptor,
            subtotal=totals["subtotal"],
            iva=totals["iva"],
            rete_fuente=retentions["rete_fuente"],
            rete_ica=retentions["rete_ica"],
            rete_iva=retentions["rete_iva"],
            total=total,
            xml_raw=xml_content,
            items=items,
        )
        return factura.normalize()

    def _unwrap_attached_document(self, tree):
        if not tree.tag.endswith("AttachedDocument"):
            return tree

        description_nodes = tree.xpath(
            "//cac:Attachment/cac:ExternalReference/cbc:Description",
            namespaces=self.namespaces,
        )
        if not description_nodes:
            return tree

        try:
            embedded_xml = ""
            for node in description_nodes:
                candidate = (node.text or "").strip()
                if "<Invoice" in candidate:
                    embedded_xml = candidate
                    break
            if not embedded_xml and description_nodes[0].text:
                embedded_xml = description_nodes[0].text
            if embedded_xml and "<" in embedded_xml:
                return etree.fromstring(embedded_xml.encode("utf-8"))
        except (XMLSyntaxError, ValueError):
            return tree

        return tree

    def _get_text(self, tree, xpath: str, default: str = "") -> str:
        result = tree.xpath(xpath, namespaces=self.namespaces)
        if result and getattr(result[0], "text", None):
            return result[0].text or default
        return default

    def _sum_texts(self, tree, xpath: str) -> float:
        values = tree.xpath(xpath, namespaces=self.namespaces)
        total = 0.0
        for node in values or []:
            total += _to_float(getattr(node, "text", None))
        return total

    def _extract_nit_proveedor(self, tree) -> str:
        nit_proveedor_raw = (
            self._get_text(tree, "//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
            or self._get_text(tree, "//cac:SenderParty/cac:PartyTaxScheme/cbc:CompanyID")
            or self._get_text(tree, "//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID")
            or ""
        )
        return _normalize_nit(nit_proveedor_raw) or "999999999"

    def _extract_nombre_proveedor(self, tree) -> str:
        return (
            self._get_text(tree, "//cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name")
            or self._get_text(tree, "//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName")
            or self._get_text(tree, "//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")
            or self._get_text(tree, "//cac:PartyName/cbc:Name")
            or "Proveedor Generico"
        )

    def _extract_nit_receptor(self, tree) -> str:
        nit_receptor_raw = (
            self._get_text(tree, "//cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID")
            or self._get_text(tree, "//cac:ReceiverParty/cac:PartyTaxScheme/cbc:CompanyID")
            or self._get_text(tree, "//cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:CompanyID")
            or ""
        )
        return _normalize_nit(nit_receptor_raw) or "123456789"

    def _extract_totals(self, tree) -> dict:
        subtotal = _to_float(self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"))
        tax_inclusive = _to_float(self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount"))
        payable_amount = _to_float(self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:PayableAmount"))
        allowances_total = _to_float(self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount"))
        charges_total = _to_float(self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:ChargeTotalAmount"))
        prepaid_amount = _to_float(
            self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:PrepaidAmount")
            or self._get_text(tree, "//cbc:PrepaidAmount")
        )
        rounding_amount = _to_float(
            self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:PayableRoundingAmount")
            or self._get_text(tree, "//cac:LegalMonetaryTotal/cbc:RoundingAmount")
        )

        iva = _to_float(
            self._get_text(
                tree,
                "//cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID='01']/cbc:TaxAmount",
            )
        )
        if iva <= 0:
            iva = _to_float(self._get_text(tree, "//cac:TaxTotal/cbc:TaxAmount"))

        return {
            "subtotal": subtotal,
            "tax_inclusive": tax_inclusive,
            "payable_amount": payable_amount,
            "allowances_total": allowances_total,
            "charges_total": charges_total,
            "prepaid_amount": prepaid_amount,
            "rounding_amount": rounding_amount,
            "iva": iva,
        }

    def _extract_retentions(self, tree) -> dict:
        rete_fuente = 0.0
        rete_ica = 0.0
        rete_iva = 0.0

        withholding_subtotals = tree.xpath(
            "//cac:WithholdingTaxTotal/cac:TaxSubtotal",
            namespaces=self.namespaces,
        )
        for subtotal_node in withholding_subtotals:
            scheme_id = ""
            scheme_name = ""

            scheme_id_nodes = subtotal_node.xpath("cac:TaxCategory/cac:TaxScheme/cbc:ID", namespaces=self.namespaces)
            if scheme_id_nodes and getattr(scheme_id_nodes[0], "text", None):
                scheme_id = scheme_id_nodes[0].text.strip().upper()

            scheme_name_nodes = subtotal_node.xpath(
                "cac:TaxCategory/cac:TaxScheme/cbc:Name",
                namespaces=self.namespaces,
            )
            if scheme_name_nodes and getattr(scheme_name_nodes[0], "text", None):
                scheme_name = scheme_name_nodes[0].text.strip().lower()

            tax_amount_nodes = subtotal_node.xpath("cbc:TaxAmount", namespaces=self.namespaces)
            amount = _to_float(tax_amount_nodes[0].text if tax_amount_nodes else None)

            if "ica" in scheme_name or scheme_id in {"08", "ICA"}:
                rete_ica += amount
            elif "fuente" in scheme_name or "renta" in scheme_name or scheme_id in {"06", "RETEFUENTE"}:
                rete_fuente += amount
            elif "iva" in scheme_name or scheme_id in {"04", "RETEIVA"}:
                rete_iva += amount

        withholding_total = self._sum_texts(tree, "//cac:WithholdingTaxTotal/cbc:TaxAmount")
        if withholding_total <= 0:
            withholding_total = rete_fuente + rete_ica + rete_iva

        if rete_fuente + rete_ica + rete_iva <= 0 and withholding_total > 0:
            rete_fuente = withholding_total

        return {
            "rete_fuente": rete_fuente,
            "rete_ica": rete_ica,
            "rete_iva": rete_iva,
            "withholding_total": withholding_total,
        }

    def _resolve_total(self, totals: dict, retentions: dict) -> float:
        subtotal = totals["subtotal"]
        iva = totals["iva"]
        tax_inclusive = totals["tax_inclusive"]
        payable_amount = totals["payable_amount"]
        allowances_total = totals["allowances_total"]
        charges_total = totals["charges_total"]
        prepaid_amount = totals["prepaid_amount"]
        rounding_amount = totals["rounding_amount"]
        withholding_total = retentions["withholding_total"]

        gross_for_formula = tax_inclusive if tax_inclusive > 0 else (subtotal + iva)
        net_from_components = (
            gross_for_formula
            + charges_total
            - allowances_total
            - prepaid_amount
            - withholding_total
            + rounding_amount
        )

        if payable_amount > 0:
            total = payable_amount
            if withholding_total > 0 and tax_inclusive > 0 and abs(payable_amount - tax_inclusive) < 0.01:
                total = net_from_components
        else:
            total = net_from_components

        if total <= 0:
            total = gross_for_formula
        return total

    def _get_line_text(self, node, xpath: str, default: str = "0") -> str:
        result = node.xpath(xpath, namespaces=self.namespaces)
        if result and getattr(result[0], "text", None):
            return result[0].text
        return default

    def _extract_items(self, tree) -> list[FacturaItem]:
        items: list[FacturaItem] = []
        lines = tree.xpath("//cac:InvoiceLine", namespaces=self.namespaces)
        for line in lines:
            descripcion = self._get_line_text(line, "cac:Item/cbc:Description", default="Articulo sin descripcion")
            cantidad = _to_float(self._get_line_text(line, "cbc:InvoicedQuantity", default="1"), default=1.0)
            precio = _to_float(self._get_line_text(line, "cac:Price/cbc:PriceAmount", default="0"))
            total_linea = _to_float(self._get_line_text(line, "cbc:LineExtensionAmount", default="0"))

            descuento = 0.0
            allowance_nodes = line.xpath(
                "cac:AllowanceCharge[cbc:ChargeIndicator='false']/cbc:Amount",
                namespaces=self.namespaces,
            )
            for node in allowance_nodes:
                descuento += _to_float(getattr(node, "text", None))

            iva_porcentaje = _to_float(
                self._get_line_text(
                    line,
                    "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
                    default="19",
                ),
                default=19.0,
            )

            items.append(
                FacturaItem(
                    descripcion=descripcion,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    descuento=descuento,
                    iva_porcentaje=iva_porcentaje,
                    total_linea=total_linea,
                )
            )

        return items

    def _parse_issue_date(self, fecha_emision_raw: str | None):
        try:
            return parser.parse(fecha_emision_raw) if fecha_emision_raw else now_bogota()
        except (ParserError, TypeError, ValueError):
            return now_bogota()


def parse_xml_dian(xml_content: str) -> FacturaDIAN:
    return DIANParser().parse(xml_content)
