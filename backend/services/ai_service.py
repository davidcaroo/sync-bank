import httpx
import logging
from config import settings

logger = logging.getLogger("ai-service")

async def clasificar_item(descripcion: str, cuentas: list, centros_costo: list | None = None):
    centros_costo = centros_costo or []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.AI_SERVICE_URL}/clasificar",
                json={"descripcion": descripcion, "cuentas": cuentas, "centros_costo": centros_costo},
                timeout=60.0
            )
            if response.status_code == 200:
                payload = response.json()
                confianza = float(payload.get("confianza") or 0.0)
                cuenta_id = payload.get("cuenta_id")
                centro_id = payload.get("centro_costo_id")

                # Avoid presenting default fallback account as a real AI suggestion
                # when confidence is effectively null.
                if confianza <= 0.0:
                    cuenta_id = None
                    centro_id = None

                return {
                    "cuenta_id": cuenta_id,
                    "centro_costo_id": centro_id,
                    "confianza": confianza,
                }
    except Exception as e:
        logger.error("ai_service_error", extra={"error": str(e)})
    
    return {
        "cuenta_id": None,
        "centro_costo_id": None,
        "confianza": 0.0,
    }
