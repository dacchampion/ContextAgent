from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List

from app.services.context_builder import build_context_json, ContextError, SymbolNotFound
from app.api.deps import DBSessionDep

router = APIRouter()

@router.get("/context",
            summary="Get technical context for a symbol",
            description="""
Builds and returns a detailed technical analysis context for a given symbol and a list of timeframes.
The context includes trend, levels, distances, zones, and summary flags.
""")
def get_context(
    db: DBSessionDep,
    symbol: str = Query(..., description="The asset symbol (e.g., BTC, AAPL)"),
    tfs: List[str] = Query(..., description="A list of timeframes (e.g., 1d, 30m)")
):
    try:
        context = build_context_json(db, symbol, tfs)
        return context
    except SymbolNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ContextError as e:
        raise HTTPException(status_code=400, detail=str(e))