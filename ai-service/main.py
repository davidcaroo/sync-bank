from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import json
import asyncio
import logging
import re

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# The ollama client resolves host on import in some versions.
os.environ.setdefault("OLLAMA_HOST", OLLAMA_URL)
import ollama

app = FastAPI(title="Sync-bank AI Service")
logger = logging.getLogger("ai-service")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "10"))

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


def _extract_json_object(text: str) -> dict:
    content = (text or "").strip()
    if not content:
        raise ValueError("Respuesta vacia del modelo")

    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: recover first JSON object from mixed text.
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("No se encontro JSON en la respuesta del modelo")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("El JSON de respuesta no es un objeto")
    return parsed

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
        parsed = _extract_json_object(content)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
