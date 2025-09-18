# app/models/ohlcv.py
from __future__ import annotations

import enum
from app.models.base import Base
from sqlalchemy import Column, BigInteger, String, Integer, SmallInteger, Numeric
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class CandleWidth(str, enum.Enum):
    d1 = "1d"
    m30 = "30m"
    m5 = "5m"
    m1 = "1m"

class Ohlcv(Base):
    __tablename__ = "ohlcv"

    # PK compuesta (coincide con tu tabla física)
    symbol_id     = Column(BigInteger, primary_key=True, nullable=False)
    candle_width  = Column(MySQLEnum(*[e.value for e in CandleWidth], name="candle_width_enum"), primary_key=True, nullable=False)
    timestamp_utc = Column(MySQLDateTime(fsp=3), primary_key=True, nullable=False)

    # Precios/volumen según tu DDL (DECIMAL)
    open_price    = Column(Numeric(18, 6), nullable=False)
    high_price    = Column(Numeric(18, 6), nullable=False)
    low_price     = Column(Numeric(18, 6), nullable=False)
    close_price   = Column(Numeric(18, 6), nullable=False)
    volume        = Column(Numeric(20, 6), nullable=True)

    provider_id   = Column(SmallInteger, nullable=False)
    # trading_date existe como columna generada en la DB; no es necesario mapearla aquí.
