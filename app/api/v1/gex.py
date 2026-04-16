from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_api_key
from app.schemas.gex import GexExposureResponse
from services.options_data import (
    OptionsDataConfigError,
    OptionsDataDependencyError,
    OptionsDataFetchError,
    fetch_options_gex,
)

router = APIRouter(
    prefix="/gex",
    tags=["gex"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/exposure-map", response_model=GexExposureResponse)
async def get_gex_exposure_map(
    ticker: str = Query(..., min_length=1, max_length=16),
    gex_filter_preset: str = Query("All"),
):
    try:
        return await fetch_options_gex(ticker=ticker, gex_filter_preset=gex_filter_preset)
    except OptionsDataConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except OptionsDataDependencyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except OptionsDataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
