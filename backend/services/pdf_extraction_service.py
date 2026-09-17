import asyncio
import io
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("pdf-extraction")

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 20
MIN_TEXT_CHARS = 80
OCR_LANGUAGE = "spa"


class PdfExtractionError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip(" .:-")
    return None


def _money(value: str | None) -> float:
    if not value:
        return 0.0
    cleaned = re.sub(r"[^\d,.-]", "", value)
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        return float(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        return 0.0


def _date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _number(text: str) -> str | None:
    return _first(
        [
            r"factura(?:\s+electr[oó]nica(?:\s+de\s+venta)?)?\s*(?:no\.?|n[uú]mero|#|:)\s*([A-Z0-9][A-Z0-9-]{2,30})",
        ],
        text,
    )


def _invoice_identity(text: str) -> str | None:
    return _first([r"\bCUFE\s*[:#]?\s*([a-fA-F0-9]{64,128})"], text) or _number(text)


def _start_signals(text: str) -> int:
    patterns = (
        r"\bCUFE\s*[:#]?\s*[a-fA-F0-9]{64,128}",
        r"factura\s+electr[oó]nica\s+de\s+venta",
        r"(?:factura|no\.?|n[uú]mero)\s*(?:no\.?|#|:)\s*[A-Z0-9][A-Z0-9-]{2,30}",
        r"\bNIT\s*[:#]?\s*[\d. -]{7,20}",
        r"fecha\s+(?:de\s+)?emisi[oó]n\s*[:#]?\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
    )
    return sum(bool(re.search(pattern, text, re.IGNORECASE)) for pattern in patterns)


def _split_page_groups(pages: list[str]) -> list[tuple[int, int, str]]:
    if not pages:
        return []
    groups: list[tuple[int, int, str]] = []
    start = 1
    current = [pages[0]]
    current_identity = _invoice_identity(pages[0])
    for page_number, text in enumerate(pages[1:], start=2):
        identity = _invoice_identity(text)
        if _start_signals(text) >= 2 and identity and identity != current_identity:
            groups.append((start, page_number - 1, "\n\n".join(current)))
            start, current, current_identity = page_number, [text], identity
        else:
            current.append(text)
            current_identity = current_identity or identity
    groups.append((start, len(pages), "\n\n".join(current)))
    return groups


def _parse_candidate(text: str, page_start: int, page_end: int) -> dict:
    cufe = _first([r"\bCUFE\s*[:#]?\s*([a-fA-F0-9]{64,128})"], text)
    nit = _first([r"\bNIT\s*[:#]?\s*([\d. -]{7,20}(?:-\d)?)"], text)
    if nit:
        nit = re.sub(r"\D", "", nit)
    issued = _first(
        [r"fecha\s+(?:de\s+)?emisi[oó]n\s*[:#]?\s*(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})"],
        text,
    )
    due = _first(
        [r"fecha\s+(?:de\s+)?vencimiento\s*[:#]?\s*(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})"],
        text,
    )
    candidate = {
        "cufe": cufe,
        "numero_factura": _number(text),
        "fecha_emision": _date(issued),
        "fecha_vencimiento": _date(due),
        "nit_proveedor": nit,
        "nombre_proveedor": None,
        "nit_receptor": None,
        "subtotal": _money(_first([r"\bsubtotal\s*[:$]?\s*([$\s\d.,-]+)"], text)),
        "iva": _money(
            _first([r"\bIVA(?:\s+\d+[,.]?\d*\s*%)?\s*[:$]?\s*([$\s\d.,-]+)"], text)
        ),
        "rete_fuente": 0,
        "rete_ica": 0,
        "rete_iva": 0,
        "total": _money(
            _first(
                [
                    r"total\s+(?:a\s+pagar|factura)\s*[:$]?\s*([$\s\d.,-]+)",
                    r"\btotal\s*[:$]\s*([$\s\d.,-]+)",
                ],
                text,
            )
        ),
        "moneda": "COP",
        "items": [],
        "page_start": page_start,
        "page_end": page_end,
        "raw_text": text,
    }
    required = ("numero_factura", "nit_proveedor", "fecha_emision", "total")
    candidate["missing_fields"] = [key for key in required if not candidate[key]]
    candidate["warnings"] = (
        ["division_manual_recomendada"] if not candidate["numero_factura"] else []
    )
    return candidate


def _extract(content: bytes) -> tuple[list[str], bool]:
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Dependencias PDF/OCR no disponibles") from exc
    if len(content) > MAX_PDF_BYTES:
        raise PdfExtractionError(413, "PDF excede 20 MB")
    if not content.startswith(b"%PDF"):
        raise PdfExtractionError(400, "El archivo no tiene una firma PDF valida")
    pages: list[str] = []
    ocr_used = False
    with fitz.open(stream=io.BytesIO(content), filetype="pdf") as document:
        if document.page_count > MAX_PDF_PAGES:
            raise PdfExtractionError(413, "PDF excede 20 paginas")
        for page in document:
            text = (page.get_text("text") or "").strip()
            if len(text) < MIN_TEXT_CHARS:
                pixmap = page.get_pixmap(dpi=200, alpha=False)
                image = Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
                text = (
                    pytesseract.image_to_string(image, lang=OCR_LANGUAGE) or ""
                ).strip()
                ocr_used = True
            pages.append(text)
    return pages, ocr_used


async def extraer_pdf_from_bytes(
    filename: str, content: bytes, *, preview: bool = True
) -> dict:
    if not filename or not filename.lower().endswith(".pdf"):
        raise PdfExtractionError(400, "Solo se aceptan archivos PDF")
    if not content:
        raise PdfExtractionError(400, "Archivo PDF vacio")
    try:
        pages, ocr_used = await asyncio.to_thread(_extract, content)
    except PdfExtractionError:
        raise
    except Exception as exc:
        logger.exception("pdf_extraction_error")
        raise PdfExtractionError(422, f"No se pudo leer el PDF: {exc}") from exc
    groups = _split_page_groups(pages)
    candidates = [_parse_candidate(text, start, end) for start, end, text in groups]
    warnings = []
    if len(groups) == 1 and len(pages) > 1 and not _invoice_identity(pages[0]):
        warnings.append("division_manual_recomendada")
    if not preview:
        warnings.append("confirmacion_humana_requerida")
    return {
        "facturas": candidates,
        "warnings": warnings,
        "raw_text": "\n\n".join(pages),
        "pages": len(pages),
        "ocr_used": ocr_used,
        "requires_review": True,
    }
