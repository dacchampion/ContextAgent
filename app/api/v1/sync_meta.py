# app/api/v1/sync_meta.py
from __future__ import annotations
import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy import select, and_, asc, desc, tuple_
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.sync_meta import SyncMeta
from app.schemas.sync_meta import SyncMetaOut, SyncMetaUpdate, SyncMetaListResponse

router = APIRouter(
    prefix="/sync-meta",
    tags=["sync-meta"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp()*1000)

def _enc_cursor(updated_ms: int, symbol_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"u": updated_ms, "s": symbol_id}).encode()).decode()

def _dec_cursor(cursor: Optional[str]) -> Optional[tuple[int, int]]:
    if not cursor: return None
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return int(d["u"]), int(d["s"])
    except Exception:
        return None

@router.get("/", response_model=SyncMetaListResponse)
def list_sync_meta(
    db: DBSessionDep,
    symbol_id: Optional[int] = Query(None),
    candle_width: Optional[str] = Query(None, pattern="^(1d|30m|5m|1m)$"),
    # filtros por ventana de actualización (cuando cambió el registro)
    start_updated_ms: Optional[int] = Query(None),
    end_updated_ms: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None, description="Cursor opaco (updated_ms, symbol_id)"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    conds = []
    if symbol_id is not None:
        conds.append(SyncMeta.symbol_id == symbol_id)
    if candle_width is not None:
        conds.append(SyncMeta.candle_width == candle_width)
    if start_updated_ms is not None:
        conds.append(SyncMeta.updated_utc >= _ms_to_dt(start_updated_ms))
    if end_updated_ms is not None:
        conds.append(SyncMeta.updated_utc < _ms_to_dt(end_updated_ms))

    after = _dec_cursor(cursor)
    if after:
        u_ms, sid = after
        key_cmp = tuple_(SyncMeta.updated_utc, SyncMeta.symbol_id)
        key_val = tuple_((_ms_to_dt(u_ms), sid))
        conds.append(key_cmp < key_val if order == "desc" else key_cmp > key_val)

    stmt = select(SyncMeta).where(and_(*conds)) if conds else select(SyncMeta)
    stmt = stmt.order_by(
        (desc if order == "desc" else asc)(SyncMeta.updated_utc),
        (desc if order == "desc" else asc)(SyncMeta.symbol_id),
    ).limit(limit + 1)

    rows = db.execute(stmt).scalars().all()
    items = rows[:limit]
    has_more = len(rows) > limit

    data = [
        SyncMetaOut(
            symbol_id=r.symbol_id,
            candle_width=r.candle_width,
            last_backfill_ms=_dt_to_ms(r.last_backfill_utc) if r.last_backfill_utc else None,
            last_realtime_ms=_dt_to_ms(r.last_realtime_utc) if r.last_realtime_utc else None,
            updated_ms=_dt_to_ms(r.updated_utc),
        )
        for r in items
    ]

    next_cursor = _enc_cursor(_dt_to_ms(items[-1].updated_utc), items[-1].symbol_id) \
        if has_more and items else None

    return SyncMetaListResponse(data=data, next_cursor=next_cursor, limit=limit)

@router.get("/{symbol_id}/{candle_width}", response_model=SyncMetaOut)
def get_sync_meta(
    db: DBSessionDep,
    symbol_id: int = Path(..., ge=1),
    candle_width: str = Path(..., pattern="^(1d|30m|5m|1m)$"),
):
    obj = db.get(SyncMeta, {"symbol_id": symbol_id, "candle_width": candle_width})
    if not obj:
        raise HTTPException(status_code=404, detail="Sync meta not found")
    return SyncMetaOut(
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        last_backfill_ms=_dt_to_ms(obj.last_backfill_utc) if obj.last_backfill_utc else None,
        last_realtime_ms=_dt_to_ms(obj.last_realtime_utc) if obj.last_realtime_utc else None,
        updated_ms=_dt_to_ms(obj.updated_utc),
    )

@router.patch("/{symbol_id}/{candle_width}", response_model=SyncMetaOut)
def upsert_sync_meta(
    db: DBSessionDep,
    symbol_id: int = Path(..., ge=1),
    candle_width: str = Path(..., pattern="^(1d|30m|5m|1m)$"),
    body: SyncMetaUpdate = ...,
):
    # upsert semántico: crea si no existe, si existe actualiza campos provistos
    obj = db.get(SyncMeta, {"symbol_id": symbol_id, "candle_width": candle_width})
    now = datetime.utcnow().replace(tzinfo=timezone.utc).replace(tzinfo=None)

    if not obj:
        obj = SyncMeta(
            symbol_id=symbol_id,
            candle_width=candle_width,
            last_backfill_utc=_ms_to_dt(body.last_backfill_ms) if body.last_backfill_ms is not None else None,
            last_realtime_utc=_ms_to_dt(body.last_realtime_ms) if body.last_realtime_ms is not None else None,
            updated_utc=now,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
    else:
        if body.last_backfill_ms is not None:
            obj.last_backfill_utc = _ms_to_dt(body.last_backfill_ms)
        if body.last_realtime_ms is not None:
            obj.last_realtime_utc = _ms_to_dt(body.last_realtime_ms)
        obj.updated_utc = now
        db.add(obj)
        db.commit()
        db.refresh(obj)

    return SyncMetaOut(
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        last_backfill_ms=_dt_to_ms(obj.last_backfill_utc) if obj.last_backfill_utc else None,
        last_realtime_ms=_dt_to_ms(obj.last_realtime_utc) if obj.last_realtime_utc else None,
        updated_ms=_dt_to_ms(obj.updated_utc),
    )
