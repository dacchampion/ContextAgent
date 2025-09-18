# app/models/indicators.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import Column, BigInteger, Numeric
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class Indicators(Base):
    __tablename__ = "indicators"

    # PK compuesta
    symbol_id     = Column(BigInteger, primary_key=True, nullable=False)
    candle_width  = Column(MySQLEnum("1d", "30m", "5m", "1m", name="cw_enum_ind"), primary_key=True, nullable=False)
    timestamp_utc = Column(MySQLDateTime(fsp=3), primary_key=True, nullable=False)

    # columnas “anchas”
    vwap   = Column(Numeric(18, 6))
    ema8   = Column(Numeric(18, 6))
    ema21  = Column(Numeric(18, 6))
    ema50  = Column(Numeric(18, 6))
    sma20  = Column(Numeric(18, 6))
    sma50  = Column(Numeric(18, 6))

    updated_utc = Column(MySQLDateTime(fsp=3), nullable=False)
