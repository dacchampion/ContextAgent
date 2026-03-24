# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Query
from typing import List

from app.api.deps import DBSessionDep
from services.context_builder import (
    build_context_json, ContextError, SymbolNotFound, NoDataError
)

router = APIRouter()

VALID_TFS = {"1D", "30m", "5m", "1m"}  # opcional

@router.get("/context")
def get_context(
    db: DBSessionDep,
    symbol: str = Query(..., min_length=1),
    tfs: str = Query("1D,30m,5m", description="Lista separada por comas: 1D,30m,5m,1m"),
):
    try:
        tf_list: List[str] = [s.strip() for s in tfs.split(",") if s.strip()]
        # Validación opcional:
        # if not tf_list or any(tf not in VALID_TFS for tf in tf_list):
        #     raise HTTPException(status_code=400, detail="Timeframe no soportado. Use 1D,30m,5m,1m")

        payload = build_context_json(db, symbol, tf_list)
        if not payload.get("timeframes"):
            raise HTTPException(status_code=404, detail="Sin datos para el símbolo/timeframes solicitados")
        return payload
    except SymbolNotFound as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ContextError as e:
        # si el error es por TF inválido u otra validación interna, 400 podría ser más semántico
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno de servidor")
