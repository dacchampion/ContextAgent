# app/models/indicator_series.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import Column, BigInteger, Integer, String, Numeric
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class IndicatorSeries(Base):
    __tablename__ = "indicator_series"

    # PK compuesta (tal cual tu DDL)
    symbol_id      = Column(BigInteger, primary_key=True, nullable=False)
    candle_width   = Column(MySQLEnum("1d", "30m", "5m", "1m", name="cw_enum_is"), primary_key=True, nullable=False)
    timestamp_utc  = Column(MySQLDateTime(fsp=3), primary_key=True, nullable=False)
    indicator_name = Column(String(32), primary_key=True, nullable=False)
    window_size    = Column(Integer, primary_key=True, nullable=False)

    indicator_value  = Column(Numeric(18, 6), nullable=False)
    indicator_method = Column(String(24), nullable=True)

    updated_utc = Column(MySQLDateTime(fsp=3), nullable=False)
