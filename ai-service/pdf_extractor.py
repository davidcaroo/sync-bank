from dataclasses import dataclass
import io

from PIL import Image
import pytesseract
from pypdf import PdfReader

@dataclass
class PageText:
    page_number: int
    text: str
    ocr_used: bool

@dataclass
class PdfExtractionResult:
    page_count: int
    pages: list[PageText]
    ocr_used: bool


def extract_pdf_text(
    pdf_bytes: bytes,
    *,
    max_pages: int,
    max_bytes: int,
    min_text_chars: int,
    ocr_lang: str,
) -> PdfExtractionResult:
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError("PyMuPDF (fitz) no disponible. Instala PyMuPDF o usa Docker.") from exc

    if max_bytes > 0 and len(pdf_bytes) > max_bytes:
        raise ValueError("PDF excede el tamano permitido")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    if max_pages > 0 and page_count > max_pages:
        raise ValueError("PDF excede el maximo de paginas permitido")

    pages: list[PageText] = []
    ocr_used_any = False

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index in range(page_count):
            page = doc.load_page(index)
            text = (page.get_text("text") or "").strip()
            ocr_used = False

            if len(text) < min_text_chars:
                pix = page.get_pixmap(dpi=200)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = (pytesseract.image_to_string(image, lang=ocr_lang) or "").strip()
                ocr_used = True

            if ocr_used:
                ocr_used_any = True

            pages.append(
                PageText(
                    page_number=index + 1,
                    text=text,
                    ocr_used=ocr_used,
                )
            )

    return PdfExtractionResult(page_count=page_count, pages=pages, ocr_used=ocr_used_any)
