# app/schemas/job_run.py
from __future__ import annotations
from typing import Optional, Any, Literal, List
from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["success", "warning", "error"]
CandleWidthLit = Literal["1d","30m","5m","1m"]

class JobRunCreate(BaseModel):
    job_name: str = Field(..., max_length=64)
    # Para “in progress” recomiendo usar "warning" (y cerrar con success/error en PATCH)
    run_status: JobStatus = "success"
    started_ms: Optional[int] = None
    symbol_id: Optional[int] = None
    candle_width: Optional[CandleWidthLit] = None
    rows_affected: Optional[int] = None
    log_message: Optional[str] = None

class JobRunUpdate(BaseModel):
    run_status: Optional[JobStatus] = None
    finished_ms: Optional[int] = None
    rows_affected: Optional[int] = None
    log_message: Optional[str] = None

class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int
    job_name: str
    symbol_id: Optional[int] = None
    candle_width: Optional[CandleWidthLit] = None
    started_ms: int
    finished_ms: Optional[int] = None
    run_status: JobStatus
    rows_affected: Optional[int] = None
    log_message: Optional[str] = None

class JobRunsResponse(BaseModel):
    data: List[JobRunOut]
    next_cursor: str | None = None
    limit: int
