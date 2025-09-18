# app/models/job_run.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import Column, BigInteger, String, Text
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class JobRun(Base):
    __tablename__ = "job_runs"

    job_id        = Column(BigInteger, primary_key=True, autoincrement=True)
    job_name      = Column(String(64), nullable=False, index=True)
    symbol_id     = Column(BigInteger, nullable=True, index=True)
    candle_width  = Column(MySQLEnum("1d","30m","5m","1m", name="cw_enum_jobs"), nullable=True, index=True)
    started_utc   = Column(MySQLDateTime(fsp=3), nullable=False, index=True)   # DEFAULT en DB
    finished_utc  = Column(MySQLDateTime(fsp=3), nullable=True)
    run_status    = Column(MySQLEnum("success","warning","error", name="run_status_enum"), nullable=False)  # DEFAULT en DB
    rows_affected = Column(BigInteger, nullable=True)
    log_message   = Column(Text, nullable=True)
