import httpx
from config import settings

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
                return {
                    "cuenta_id": payload.get("cuenta_id") or settings.ALEGRA_CUENTA_DEFAULT_GASTOS,
                    "centro_costo_id": payload.get("centro_costo_id") or None,
                    "confianza": payload.get("confianza", 0.0),
                }
    except Exception as e:
        print(f"Error calling AI service: {e}")
    
    return {
        "cuenta_id": settings.ALEGRA_CUENTA_DEFAULT_GASTOS,
        "centro_costo_id": None,
        "confianza": 0.0,
    }
