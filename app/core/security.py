# app/core/security.py
import hmac
from fastapi import Header, HTTPException, status
from app.core.config import settings

async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    keys = settings.api_keys_list  # <- SIEMPRE la lista normalizada

    if not keys:
        # En dev puedes dejar pasar si no hay llaves configuradas.
        # En prod, mejor forzar 401 si quieres estricto.
        return

    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    for k in keys:
        if hmac.compare_digest(k, x_api_key.strip().strip('"').strip("'")):
            return

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
