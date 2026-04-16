# app/api/v1/__init__.py
from fastapi import APIRouter

from .health import router as health_router
from .symbols import router as symbols_router
from .ohlcv import router as ohlcv_router
from .indicators import router as indicators_router
from .indicator_series import router as indicator_series_router
from .anchors import router as anchors_router
from .sync_meta import router as sync_meta_router
from .job_runs import router as job_runs_router
from .gex import router as gex_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(symbols_router)
api_router.include_router(ohlcv_router)
api_router.include_router(indicators_router)
api_router.include_router(indicator_series_router)
api_router.include_router(anchors_router)
api_router.include_router(sync_meta_router)
api_router.include_router(job_runs_router)
api_router.include_router(gex_router)
