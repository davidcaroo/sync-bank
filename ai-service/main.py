from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import ollama
import os
import json

app = FastAPI(title="Sync-bank AI Service")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

class ClasificarRequest(BaseModel):
    descripcion: str
    cuentas: List[dict] = [] # List of {id: x, nombre: y}
    centros_costo: List[dict] = [] # List of {id: x, nombre: y}

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
        response = ollama.chat(model=OLLAMA_MODEL, messages=[
            {'role': 'system', 'content': 'Responde siempre en formato JSON.'},
            {'role': 'user', 'content': prompt},
        ])
        
        content = response['message']['content']
        # Clean potential markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(content)
        
        return ClasificarResponse(
            cuenta_id=str(parsed.get("cuenta_id", "")),
            cuenta_nombre=parsed.get("cuenta_nombre", ""),
            centro_costo_id=str(parsed.get("centro_costo_id", "")),
            centro_costo_nombre=parsed.get("centro_costo_nombre", ""),
            confianza=parsed.get("confianza", 0.5)
        )
    except Exception as e:
        print(f"Ollama Error: {e}")
        return ClasificarResponse(confianza=0.0)

@app.get("/health")
async def health():
    try:
        models = ollama.list()
        return {"status": "ok", "ollama": "connected", "models": models}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
