# app/api/v1/job_runs.py
from __future__ import annotations
import base64, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy import select, and_, asc, desc, tuple_
from app.core.security import require_api_key
from app.api.deps import DBSessionDep
from app.models.job_run import JobRun
from app.schemas.job_run import JobRunCreate, JobRunUpdate, JobRunOut, JobRunsResponse

router = APIRouter(
    prefix="/job-runs",
    tags=["job-runs"],
    dependencies=[Depends(require_api_key)],
)

def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(tzinfo=None)

def _dt_to_ms(dt: datetime | None) -> int | None:
    if dt is None: return None
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

def _enc(ts_ms: int, jid: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"ts": ts_ms, "id": jid}).encode()).decode()

def _dec(cursor: Optional[str]) -> Optional[tuple[int, int]]:
    if not cursor: return None
    try:
        d = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return int(d["ts"]), int(d["id"])
    except Exception:
        return None

@router.get("/", response_model=JobRunsResponse)
def list_job_runs(
    db: DBSessionDep,
    job_name: Optional[str] = Query(None),
    run_status: Optional[str] = Query(None, pattern="^(success|warning|error)$"),
    symbol_id: Optional[int] = Query(None),
    candle_width: Optional[str] = Query(None, pattern="^(1d|30m|5m|1m)$"),
    start_ms: Optional[int] = Query(None, description="started_utc >= start_ms"),
    end_ms: Optional[int] = Query(None, description="started_utc < end_ms"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: Optional[str] = Query(None, description="Cursor (started_ms, job_id)"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    conds = []
    if job_name:   conds.append(JobRun.job_name == job_name)
    if run_status: conds.append(JobRun.run_status == run_status)
    if symbol_id is not None: conds.append(JobRun.symbol_id == symbol_id)
    if candle_width is not None: conds.append(JobRun.candle_width == candle_width)
    if start_ms is not None: conds.append(JobRun.started_utc >= _ms_to_dt(start_ms))
    if end_ms   is not None: conds.append(JobRun.started_utc <  _ms_to_dt(end_ms))

    after = _dec(cursor)
    if after:
        ts, jid = after
        key = tuple_(JobRun.started_utc, JobRun.job_id)
        val = tuple_((_ms_to_dt(ts), jid))
        conds.append(key < val if order == "desc" else key > val)

    stmt = select(JobRun).where(and_(*conds)) if conds else select(JobRun)
    stmt = stmt.order_by(
        (desc if order == "desc" else asc)(JobRun.started_utc),
        (desc if order == "desc" else asc)(JobRun.job_id),
    ).limit(limit + 1)

    rows = db.execute(stmt).scalars().all()
    items = rows[:limit]
    has_more = len(rows) > limit

    data = [
        JobRunOut(
            job_id=r.job_id,
            job_name=r.job_name,
            symbol_id=r.symbol_id,
            candle_width=r.candle_width,
            started_ms=_dt_to_ms(r.started_utc),
            finished_ms=_dt_to_ms(r.finished_utc),
            run_status=r.run_status,
            rows_affected=r.rows_affected,
            log_message=r.log_message,
        )
        for r in items
    ]

    next_cursor = _enc(_dt_to_ms(items[-1].started_utc), items[-1].job_id) if has_more and items else None
    return JobRunsResponse(data=data, next_cursor=next_cursor, limit=limit)

@router.get("/{job_id}", response_model=JobRunOut)
def get_job_run(db: DBSessionDep, job_id: int = Path(..., ge=1)):
    r = db.get(JobRun, job_id)
    if not r:
        raise HTTPException(status_code=404, detail="Job run not found")
    return JobRunOut(
        job_id=r.job_id,
        job_name=r.job_name,
        symbol_id=r.symbol_id,
        candle_width=r.candle_width,
        started_ms=_dt_to_ms(r.started_utc),
        finished_ms=_dt_to_ms(r.finished_utc),
        run_status=r.run_status,
        rows_affected=r.rows_affected,
        log_message=r.log_message,
    )

@router.post("/", response_model=JobRunOut, status_code=status.HTTP_201_CREATED)
def create_job_run(db: DBSessionDep, body: JobRunCreate):
    # started_utc y run_status tienen DEFAULT en DB, pero permitimos override desde API
    now = datetime.utcnow().replace(tzinfo=timezone.utc).replace(tzinfo=None)
    started = _ms_to_dt(body.started_ms) if body.started_ms is not None else now
    obj = JobRun(
        job_name=body.job_name,
        symbol_id=body.symbol_id,
        candle_width=body.candle_width,
        started_utc=started,
        finished_utc=None,
        run_status=body.run_status,
        rows_affected=body.rows_affected,
        log_message=body.log_message,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return JobRunOut(
        job_id=obj.job_id,
        job_name=obj.job_name,
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        started_ms=_dt_to_ms(obj.started_utc),
        finished_ms=_dt_to_ms(obj.finished_utc),
        run_status=obj.run_status,
        rows_affected=obj.rows_affected,
        log_message=obj.log_message,
    )

@router.patch("/{job_id}", response_model=JobRunOut)
def update_job_run(
    db: DBSessionDep,
    job_id: int = Path(..., ge=1),
    body: JobRunUpdate = ...,
):
    obj = db.get(JobRun, job_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Job run not found")

    if body.run_status is not None:
        obj.run_status = body.run_status
    if body.finished_ms is not None:
        obj.finished_utc = _ms_to_dt(body.finished_ms)
    if body.rows_affected is not None:
        obj.rows_affected = body.rows_affected
    if body.log_message is not None:
        obj.log_message = body.log_message

    db.add(obj); db.commit(); db.refresh(obj)

    return JobRunOut(
        job_id=obj.job_id,
        job_name=obj.job_name,
        symbol_id=obj.symbol_id,
        candle_width=obj.candle_width,
        started_ms=_dt_to_ms(obj.started_utc),
        finished_ms=_dt_to_ms(obj.finished_utc),
        run_status=obj.run_status,
        rows_affected=obj.rows_affected,
        log_message=obj.log_message,
    )
