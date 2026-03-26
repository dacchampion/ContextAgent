# app/api/v1/indicators.py
from __future__ import annotations
import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, asc
from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.indicators import Indicators
from app.schemas.indicators import IndicatorsRow, IndicatorsResponse

router = APIRouter(
    prefix="/indicators",
    tags=["indicators"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp()*1000)

def _enc(ts_ms: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts_ms}).encode()).decode()

def _dec(cursor: Optional[str]) -> Optional[int]:
    if not cursor: return None
    try:
        return int(json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())["ts"])
    except Exception:
        return None

@router.get("/", response_model=IndicatorsResponse)
def list_indicators(
    db: DBSessionDep,
    symbol_id: int = Query(..., description="ID del símbolo"),
    candle_width: str = Query(..., pattern="^(1d|30m|5m|1m)$"),
    start_ms: Optional[int] = Query(None),
    end_ms: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    cursor: Optional[str] = Query(None),
):
    conds = [
        Indicators.symbol_id == symbol_id,
        Indicators.candle_width == candle_width,
    ]
    if start_ms is not None: conds.append(Indicators.timestamp_utc >= _ms_to_dt(start_ms))
    if end_ms   is not None: conds.append(Indicators.timestamp_utc <  _ms_to_dt(end_ms))
    after = _dec(cursor)
    if after is not None: conds.append(Indicators.timestamp_utc > _ms_to_dt(after))

    stmt = (select(Indicators)
            .where(and_(*conds))
            .order_by(asc(Indicators.timestamp_utc))
            .limit(limit+1))

    rows = db.execute(stmt).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]

    data = []
    for r in items:
        data.append(IndicatorsRow.model_validate({
            "symbol_id": r.symbol_id,
            "candle_width": r.candle_width,
            "timestamp_ms": _dt_to_ms(r.timestamp_utc),
            "vwap": r.vwap, "ema8": r.ema8, "ema21": r.ema21, "ema50": r.ema50,
            "sma20": r.sma20, "sma50": r.sma50,
            "bb_mid": r.bb_mid, "bb_up": r.bb_up, "bb_dn": r.bb_dn, "bb_percB": r.bb_percB, "bb_bw": r.bb_bw,
            "kc_mid": r.kc_mid, "kc_up": r.kc_up, "kc_dn": r.kc_dn,
            "updated_ms": _dt_to_ms(r.updated_utc),
        }))

    next_cursor = _enc(_dt_to_ms(items[-1].timestamp_utc)) if has_more and items else None
    return IndicatorsResponse(data=data, next_cursor=next_cursor, limit=limit)
