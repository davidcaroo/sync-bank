from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import json
import asyncio
import logging

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# The ollama client resolves host on import in some versions.
os.environ.setdefault("OLLAMA_HOST", OLLAMA_URL)
import ollama

from llm_utils import extract_json_object
from pdf_extractor import extract_pdf_text
from pdf_mapper import map_text_to_facturas
from pdf_models import ExtraerPdfResponse

app = FastAPI(title="Sync-bank AI Service")
logger = logging.getLogger("ai-service")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "10"))
PDF_MAX_BYTES = int(os.getenv("PDF_MAX_BYTES", "15000000"))
PDF_MAX_PAGES = int(os.getenv("PDF_MAX_PAGES", "5"))
PDF_OCR_LANG = os.getenv("PDF_OCR_LANG", "spa")
PDF_MIN_TEXT_CHARS = int(os.getenv("PDF_MIN_TEXT_CHARS", "30"))
PDF_MAX_PROMPT_CHARS = int(os.getenv("PDF_MAX_PROMPT_CHARS", "12000"))
PDF_RETRY_PROMPT_CHARS = int(os.getenv("PDF_RETRY_PROMPT_CHARS", "4000"))

class ClasificarRequest(BaseModel):
    descripcion: str
    cuentas: List[dict] = Field(default_factory=list)  # List of {id: x, nombre: y}
    centros_costo: List[dict] = Field(default_factory=list)  # List of {id: x, nombre: y}

class ClasificarResponse(BaseModel):
    cuenta_id: Optional[str] = None
    cuenta_nombre: Optional[str] = None
    centro_costo_id: Optional[str] = None
    centro_costo_nombre: Optional[str] = None
    confianza: float


@app.post("/clasificar", response_model=ClasificarResponse)
async def clasificar(req: ClasificarRequest):
    prompt = f"""
    Eres un contador colombiano experto en PUC y gestión de costos.
    Dado el siguiente item de factura: "{req.descripcion}"
    
    1. Selecciona la CUENTA CONTABLE mas apropiada de esta lista:
    {json.dumps(req.cuentas)}
    
    2. Selecciona el CENTRO DE COSTO mas apropiado de esta lista:
    {json.dumps(req.centros_costo)}
    
    Responde SOLO con un JSON valido con esta estructura:
    {{
        "cuenta_id": "xxx", 
        "cuenta_nombre": "xxx", 
        "centro_costo_id": "xxx",
        "centro_costo_nombre": "xxx",
        "confianza": 0.0
    }}
    """
    
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": "Responde siempre en formato JSON."},
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )

        content = response.get("message", {}).get("content", "")
        parsed = extract_json_object(content)
        confianza = float(parsed.get("confianza", 0.0))
        confianza = max(0.0, min(confianza, 1.0))

        return ClasificarResponse(
            cuenta_id=str(parsed.get("cuenta_id", "")),
            cuenta_nombre=parsed.get("cuenta_nombre", ""),
            centro_costo_id=str(parsed.get("centro_costo_id", "")),
            centro_costo_nombre=parsed.get("centro_costo_nombre", ""),
            confianza=confianza,
        )
    except TimeoutError:
        logger.warning("ollama_timeout", extra={"timeout_seconds": OLLAMA_TIMEOUT_SECONDS})
        return ClasificarResponse(confianza=0.0)
    except Exception as e:
        logger.exception("ollama_error", extra={"error": str(e)})
        return ClasificarResponse(confianza=0.0)

@app.get("/health")
async def health():
    try:
        models = await asyncio.wait_for(
            asyncio.to_thread(ollama.list),
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        return {"status": "ok", "ollama": "connected", "models": models}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/extraer-pdf", response_model=ExtraerPdfResponse)
async def extraer_pdf(file: UploadFile = File(...), preview: bool = True):
    filename = file.filename or "sin_nombre"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer archivo: {exc}")

    try:
        extraction = await asyncio.to_thread(
            extract_pdf_text,
            content,
            max_pages=PDF_MAX_PAGES,
            max_bytes=PDF_MAX_BYTES,
            min_text_chars=PDF_MIN_TEXT_CHARS,
            ocr_lang=PDF_OCR_LANG,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except Exception as exc:
        logger.exception("pdf_extraction_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Error extrayendo PDF")

    raw_text = "\n\n".join([page.text for page in extraction.pages if page.text])
    facturas, confianza, warnings = await map_text_to_facturas(
        raw_text,
        model=OLLAMA_MODEL,
        timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        max_chars=PDF_MAX_PROMPT_CHARS,
        retry_timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        retry_max_chars=PDF_RETRY_PROMPT_CHARS,
    )

    if preview is False:
        warnings.append("persistencia_no_implementada")

    return ExtraerPdfResponse(
        facturas=facturas,
        confianza=confianza,
        warnings=warnings,
        raw_text=raw_text,
        pages=extraction.page_count,
        ocr_used=extraction.ocr_used,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
