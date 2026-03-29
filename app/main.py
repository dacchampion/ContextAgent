from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from starlette.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.api.v1 import api_router
from app.api.v1.context import router as context_router
from app.api.v1.narrative import router as narrative_router
from app.middleware.request_id import RequestIDMiddleware
from app.core.logging import setup_logging

setup_logging()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        routes=app.routes,
    )
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    # por defecto exigirlo (los endpoints que no tienen dep se siguen viendo sin auth)
    for path in openapi_schema.get("paths", {}).values():
        for op in path.values():
            sec = op.get("security", [])
            sec.append({"ApiKeyAuth": []})
            op["security"] = sec
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.cors_origins_list],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Montar API v1
app.include_router(context_router)
app.include_router(narrative_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestIDMiddleware)
app.openapi = custom_openapi


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "docs": f"{settings.API_V1_STR}/docs",
        "openapi": f"{settings.API_V1_STR}/openapi.json",
    }
