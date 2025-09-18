# app/models/sync_meta.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import Column, BigInteger
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class SyncMeta(Base):
    __tablename__ = "sync_meta"

    symbol_id        = Column(BigInteger, primary_key=True, nullable=False)
    candle_width     = Column(MySQLEnum("1d", "30m", "5m", "1m", name="cw_enum_sync"), primary_key=True, nullable=False)
    last_backfill_utc = Column(MySQLDateTime(fsp=3), nullable=True)
    last_realtime_utc = Column(MySQLDateTime(fsp=3), nullable=True)
    updated_utc       = Column(MySQLDateTime(fsp=3), nullable=False)
