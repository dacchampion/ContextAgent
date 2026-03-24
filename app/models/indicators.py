# app/models/indicators.py
from __future__ import annotations

from sqlalchemy import (
    Column, BigInteger, DateTime, Enum, Float, String,
    PrimaryKeyConstraint, Index, ForeignKey
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Indicators(Base):
    __tablename__ = "indicators"

    symbol_id = Column(BigInteger, ForeignKey("symbols.symbol_id"), nullable=False)
    candle_width = Column(Enum("1d", "30m", "5m", "1m", name="cw_enum"), nullable=False)
    timestamp_utc = Column(DateTime(timezone=False), nullable=False)

    # core
    vwap  = Column(Float, nullable=True)
    ema8  = Column(Float, nullable=True)
    ema21 = Column(Float, nullable=True)
    ema50 = Column(Float, nullable=True)
    sma20 = Column(Float, nullable=True)
    sma50 = Column(Float, nullable=True)

    # 🔥 Bollinger (agregados por la migración)
    bb_mid   = Column(Float, nullable=True)
    bb_up    = Column(Float, nullable=True)
    bb_dn    = Column(Float, nullable=True)
    bb_percB = Column(Float, nullable=True)
    bb_bw    = Column(Float, nullable=True)

    updated_utc = Column(DateTime(timezone=False), nullable=False)

    __table_args__ = (
        # PK compuesta como en tu schema
        PrimaryKeyConstraint("symbol_id", "candle_width", "timestamp_utc", name="pk_indicators"),
        # Índices acorde a tu migración (opcional aquí; ya existen en DB)
        Index("ind_sid_cw_ts", "symbol_id", "candle_width", "timestamp_utc", unique=False),
        # Index unique para upserts
        Index("uniq_sid_cw_ts", "symbol_id", "candle_width", "timestamp_utc", unique=True),
    )
