import httpx
import logging

from config import settings

logger = logging.getLogger("pdf-extraction")

class PdfExtractionError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

async def extraer_pdf_from_bytes(filename: str, content: bytes, *, preview: bool = True) -> dict:
    if not filename or not filename.lower().endswith(".pdf"):
        raise PdfExtractionError(400, "Solo se aceptan archivos PDF")
    if not content:
        raise PdfExtractionError(400, "Archivo PDF vacio")

    files = {
        "file": (filename, content, "application/pdf"),
    }
    params = {
        "preview": "true" if preview else "false",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{settings.AI_SERVICE_URL}/extraer-pdf",
                files=files,
                params=params,
            )
    except httpx.RequestError as exc:
        logger.error(
            "ai_service_unreachable",
            extra={"error": str(exc), "ai_service_url": settings.AI_SERVICE_URL},
        )
        raise PdfExtractionError(
            502,
            f"No se pudo contactar ai-service ({settings.AI_SERVICE_URL}): {exc}",
        )

    if response.status_code != 200:
        detail = None
        try:
            payload = response.json()
            detail = payload.get("detail")
        except Exception:
            detail = response.text
        raise PdfExtractionError(response.status_code, str(detail))

    return response.json()
