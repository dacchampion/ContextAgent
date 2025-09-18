# app/models/avwap_anchor.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import Column, BigInteger, String
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime, ENUM as MySQLEnum

class AvwapAnchor(Base):
    __tablename__ = "avwap_anchors"

    anchor_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id     = Column(BigInteger, nullable=False, index=True)
    candle_width  = Column(MySQLEnum("1d", "30m", "5m", "1m", name="cw_enum_anchor"), nullable=False, index=True)
    anchor_ts_utc = Column(MySQLDateTime(fsp=3), nullable=False, index=True)
    anchor_type   = Column(MySQLEnum(
        "session_open", "weekly_open", "monthly_open", "swing_high", "swing_low", "custom_event",
        name="anchor_type_enum"
    ), nullable=False, index=True)
    anchor_label  = Column(String(64), nullable=True)
    created_utc   = Column(MySQLDateTime(fsp=3), nullable=False)
