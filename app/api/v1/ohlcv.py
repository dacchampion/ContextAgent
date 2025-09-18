# app/api/v1/ohlcv.py
from __future__ import annotations

import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, asc
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.ohlcv import Ohlcv, CandleWidth
from app.schemas.ohlcv import OhlcvOut, OhlcvResponse

router = APIRouter(
    prefix="/ohlcv",
    tags=["ohlcv"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    # Epoch ms -> naive UTC datetime (coincide con DATETIME(3) en DB)
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime) -> int:
    # naive UTC datetime -> epoch ms
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

def _enc_cursor(ts_ms: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts_ms}).encode()).decode()

def _dec_cursor(cursor: Optional[str]) -> Optional[int]:
    if not cursor:
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        v = int(d["ts"])
        return v
    except Exception:
        return None

@router.get("/", response_model=OhlcvResponse)
def list_ohlcv(
    db: DBSessionDep,
    symbol_id: int = Query(..., description="ID del símbolo"),
    candle_width: CandleWidth | str = Query(..., description="1m, 5m, 30m, 1d"),
    start_ms: Optional[int] = Query(None, description="Epoch ms (inclusive)"),
    end_ms: Optional[int] = Query(None, description="Epoch ms (exclusive)"),
    limit: int = Query(500, ge=1, le=5000),
    cursor: Optional[str] = Query(None),
):
    # Normaliza candle_width si vino como str
    if isinstance(candle_width, str):
        if candle_width not in {e.value for e in CandleWidth}:
            raise HTTPException(status_code=400, detail="Invalid candle_width")
        cw_val = candle_width
    else:
        cw_val = candle_width.value

    conds = [
        Ohlcv.symbol_id == symbol_id,
        Ohlcv.candle_width == cw_val,
    ]
    if start_ms is not None:
        conds.append(Ohlcv.timestamp_utc >= _ms_to_dt(start_ms))
    if end_ms is not None:
        conds.append(Ohlcv.timestamp_utc < _ms_to_dt(end_ms))

    after_ms = _dec_cursor(cursor)
    if after_ms is not None:
        conds.append(Ohlcv.timestamp_utc > _ms_to_dt(after_ms))

    stmt = (
        select(Ohlcv)
        .where(and_(*conds))
        .order_by(asc(Ohlcv.timestamp_utc))
        .limit(limit + 1)
    )

    rows = db.execute(stmt).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]

    data: list[OhlcvOut] = []
    for r in items:
        data.append(
            OhlcvOut.model_validate(
                {
                    "symbol_id": r.symbol_id,
                    "candle_width": r.candle_width,
                    "timestamp_ms": _dt_to_ms(r.timestamp_utc),
                    "open_price": r.open_price,
                    "high_price": r.high_price,
                    "low_price": r.low_price,
                    "close_price": r.close_price,
                    "volume": r.volume,
                    "provider_id": r.provider_id,
                }
            )
        )

    next_cursor = _enc_cursor(_dt_to_ms(items[-1].timestamp_utc)) if has_more and items else None
    return OhlcvResponse(data=data, next_cursor=next_cursor, limit=limit)
