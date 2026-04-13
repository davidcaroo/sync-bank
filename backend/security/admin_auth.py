from fastapi import Header, HTTPException
from config import settings


def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin key no configurada")
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="No autorizado")
