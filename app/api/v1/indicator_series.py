# app/api/v1/indicator_series.py
from __future__ import annotations
import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, asc, tuple_
from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.indicator_series import IndicatorSeries
from app.schemas.indicator_series import IndicatorPointOut, IndicatorSeriesResponse

router = APIRouter(
    prefix="/indicator-series",
    tags=["indicator-series"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp()*1000)

def _enc(ts_ms: int, name: str, window: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts_ms, "n": name, "w": window}).encode()).decode()

def _dec(cursor: Optional[str]) -> Optional[tuple[int, str, int]]:
    if not cursor: return None
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return int(d["ts"]), str(d["n"]), int(d["w"])
    except Exception:
        return None

@router.get("/", response_model=IndicatorSeriesResponse)
def list_indicator_series(
    db: DBSessionDep,
    symbol_id: int = Query(...),
    candle_width: str = Query(..., pattern="^(1d|30m|5m|1m)$"),
    indicator_name: Optional[str] = Query(None, description="Filtra por familia (e.g., 'EMA','SMA','VWAP', 'AVWAP')"),
    window_size: Optional[int] = Query(None, ge=1, description="Filtra por ventana (e.g., 8,21,50)"),
    method: Optional[str] = Query(None, alias="indicator_method"),
    start_ms: Optional[int] = Query(None),
    end_ms: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    cursor: Optional[str] = Query(None),
):
    conds = [
        IndicatorSeries.symbol_id == symbol_id,
        IndicatorSeries.candle_width == candle_width,
    ]
    if indicator_name is not None:
        conds.append(IndicatorSeries.indicator_name == indicator_name)
    if window_size is not None:
        conds.append(IndicatorSeries.window_size == window_size)
    if method is not None:
        conds.append(IndicatorSeries.indicator_method == method)

    if start_ms is not None:
        conds.append(IndicatorSeries.timestamp_utc >= _ms_to_dt(start_ms))
    if end_ms is not None:
        conds.append(IndicatorSeries.timestamp_utc < _ms_to_dt(end_ms))

    after = _dec(cursor)
    if after is not None:
        ts, n, w = after
        # Orden total para paginar determinísticamente
        conds.append(
            tuple_(IndicatorSeries.timestamp_utc, IndicatorSeries.indicator_name, IndicatorSeries.window_size)
            > tuple_((_ms_to_dt(ts), n, w))
        )

    stmt = (
        select(IndicatorSeries)
        .where(and_(*conds))
        .order_by(
            asc(IndicatorSeries.timestamp_utc),
            asc(IndicatorSeries.indicator_name),
            asc(IndicatorSeries.window_size),
        )
        .limit(limit + 1)
    )

    rows = db.execute(stmt).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]

    data = [
        IndicatorPointOut.model_validate({
            "symbol_id": r.symbol_id,
            "candle_width": r.candle_width,
            "timestamp_ms": _dt_to_ms(r.timestamp_utc),
            "indicator_name": r.indicator_name,
            "window_size": r.window_size,
            "indicator_value": r.indicator_value,
            "indicator_method": r.indicator_method,
        })
        for r in items
    ]

    next_cursor = _enc(
        _dt_to_ms(items[-1].timestamp_utc),
        items[-1].indicator_name,
        items[-1].window_size,
    ) if has_more and items else None

    return IndicatorSeriesResponse(data=data, next_cursor=next_cursor, limit=limit)
