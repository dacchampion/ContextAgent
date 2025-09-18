# app/api/v1/anchors.py
from __future__ import annotations

import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy import select, and_, asc, desc, tuple_
from sqlalchemy.exc import IntegrityError

from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.avwap_anchor import AvwapAnchor
from app.schemas.avwap_anchor import AnchorsResponse, AnchorOut, AnchorCreate, AnchorUpdate

router = APIRouter(
    prefix="/anchors",
    tags=["anchors"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    # epoch ms -> naive UTC datetime (para DATETIME(3) MySQL)
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime) -> int:
    # naive UTC datetime -> epoch ms
    return int(dt.replace(tzinfo=timezone.utc).timestamp()*1000)

def _enc(ts_ms: int, aid: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts_ms, "id": aid}).encode()).decode()

def _dec(cursor: Optional[str]) -> Optional[tuple[int, int]]:
    if not cursor:
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return int(d["ts"]), int(d["id"])
    except Exception:
        return None

@router.get("/", response_model=AnchorsResponse)
def list_anchors(
    db: DBSessionDep,
    symbol_id: int = Query(..., description="ID del símbolo"),
    candle_width: Optional[str] = Query(None, pattern="^(1d|30m|5m|1m)$"),
    anchor_type: Optional[str] = Query(None, description="session_open,weekly_open,monthly_open,swing_high,swing_low,custom_event"),
    start_ms: Optional[int] = Query(None, description="Epoch ms (inclusive)"),
    end_ms: Optional[int] = Query(None, description="Epoch ms (exclusive)"),
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    conds = [AvwapAnchor.symbol_id == symbol_id]
    if candle_width:
        conds.append(AvwapAnchor.candle_width == candle_width)
    if anchor_type:
        conds.append(AvwapAnchor.anchor_type == anchor_type)
    if start_ms is not None:
        conds.append(AvwapAnchor.anchor_ts_utc >= _ms_to_dt(start_ms))
    if end_ms is not None:
        conds.append(AvwapAnchor.anchor_ts_utc < _ms_to_dt(end_ms))

    after = _dec(cursor)
    if after:
        ts, aid = after
        cmp = tuple_(AvwapAnchor.anchor_ts_utc, AvwapAnchor.anchor_id)
        val = tuple_((_ms_to_dt(ts), aid))
        conds.append(cmp > val if order == "asc" else cmp < val)

    stmt = select(AvwapAnchor).where(and_(*conds))
    stmt = stmt.order_by(
        (asc if order == "asc" else desc)(AvwapAnchor.anchor_ts_utc),
        (asc if order == "asc" else desc)(AvwapAnchor.anchor_id),
    ).limit(limit + 1)

    rows = db.execute(stmt).scalars().all()
    items = rows[:limit]
    has_more = len(rows) > limit

    data = [
        AnchorOut(
            anchor_id=r.anchor_id,
            symbol_id=r.symbol_id,
            candle_width=r.candle_width,
            anchor_type=r.anchor_type,
            anchor_ms=_dt_to_ms(r.anchor_ts_utc),
            anchor_label=r.anchor_label,
            created_ms=_dt_to_ms(r.created_utc),
        )
        for r in items
    ]
    next_cursor = _enc(_dt_to_ms(items[-1].anchor_ts_utc), items[-1].anchor_id) if has_more and items else None
    return AnchorsResponse(data=data, next_cursor=next_cursor, limit=limit)

@router.post("/", response_model=AnchorOut, status_code=status.HTTP_201_CREATED)
def create_anchor(
    db: DBSessionDep,
    body: AnchorCreate,
    on_conflict: str = Query("error", pattern="^(error|return|update_label)$"),
):
    # ¿existe ya?
    from sqlalchemy import select, and_
    exists_stmt = select(AvwapAnchor).where(and_(
        AvwapAnchor.symbol_id == body.symbol_id,
        AvwapAnchor.candle_width == body.candle_width,
        AvwapAnchor.anchor_type == body.anchor_type,
        AvwapAnchor.anchor_ts_utc == _ms_to_dt(body.anchor_ms),
    )).limit(1)
    existing = db.execute(exists_stmt).scalars().first()

    if existing:
        if on_conflict == "return":
            return AnchorOut(
                anchor_id=existing.anchor_id,
                symbol_id=existing.symbol_id,
                candle_width=existing.candle_width,
                anchor_type=existing.anchor_type,
                anchor_ms=_dt_to_ms(existing.anchor_ts_utc),
                anchor_label=existing.anchor_label,
                created_ms=_dt_to_ms(existing.created_utc),
            )
        if on_conflict == "update_label":
            # solo cambia el label si viene en el body
            if body.anchor_label is not None and body.anchor_label != existing.anchor_label:
                existing.anchor_label = body.anchor_label
                db.add(existing); db.commit(); db.refresh(existing)
            return AnchorOut(
                anchor_id=existing.anchor_id,
                symbol_id=existing.symbol_id,
                candle_width=existing.candle_width,
                anchor_type=existing.anchor_type,
                anchor_ms=_dt_to_ms(existing.anchor_ts_utc),
                anchor_label=existing.anchor_label,
                created_ms=_dt_to_ms(existing.created_utc),
            )
        # default: error explícito
        raise HTTPException(status_code=409, detail="Anchor already exists for given (symbol_id, candle_width, ts, type)")

    # crear nuevo
    obj = AvwapAnchor(
        symbol_id=body.symbol_id,
        candle_width=body.candle_width,
        anchor_type=body.anchor_type,
        anchor_ts_utc=_ms_to_dt(body.anchor_ms),
        anchor_label=body.anchor_label,
        created_utc=datetime.utcnow().replace(tzinfo=timezone.utc).replace(tzinfo=None),
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return AnchorOut(
        anchor_id=obj.anchor_id,
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        anchor_type=obj.anchor_type,
        anchor_ms=_dt_to_ms(obj.anchor_ts_utc),
        anchor_label=obj.anchor_label,
        created_ms=_dt_to_ms(obj.created_utc),
    )

@router.patch("/{anchor_id}", response_model=AnchorOut)
def update_anchor(
    db: DBSessionDep,
    anchor_id: int = Path(..., ge=1),
    body: AnchorUpdate = ...,
):
    obj = db.get(AvwapAnchor, anchor_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Anchor not found")

    # OJO: cambiar ts/type/candle_width puede violar la UNIQUE; lo permitimos pero capturamos conflicto.
    if body.anchor_ms is not None:
        obj.anchor_ts_utc = _ms_to_dt(body.anchor_ms)
    if body.anchor_type is not None:
        obj.anchor_type = body.anchor_type
    if body.anchor_label is not None:
        obj.anchor_label = body.anchor_label

    try:
        db.add(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Update would duplicate an existing anchor (unique constraint)")
    db.refresh(obj)

    return AnchorOut(
        anchor_id=obj.anchor_id,
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        anchor_type=obj.anchor_type,
        anchor_ms=_dt_to_ms(obj.anchor_ts_utc),
        anchor_label=obj.anchor_label,
        created_ms=_dt_to_ms(obj.created_utc),
    )

@router.delete("/{anchor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_anchor(db: DBSessionDep, anchor_id: int = Path(..., ge=1)):
    obj = db.get(AvwapAnchor, anchor_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Anchor not found")
    db.delete(obj)
    db.commit()
    return None
