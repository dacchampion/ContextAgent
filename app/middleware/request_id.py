from __future__ import annotations

import uuid
import contextvars
from typing import Callable, Awaitable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp
from starlette.responses import Response

# ContextVar para inyectar el request-id en logs
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    - Lee X-Request-ID si viene; si no, genera uno (uuid4).
    - Lo pone en request.state.request_id y en un ContextVar para logging.
    - Lo devuelve en la respuesta como X-Request-ID.
    """
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        token = request_id_ctx.set(rid)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            # restaurar el contexto
            request_id_ctx.reset(token)
        # devolver el header
        response.headers[self.header_name] = rid
        return response

def get_request_id() -> str:
    return request_id_ctx.get()
