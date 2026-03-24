# app/models/avwap_anchors.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, BigInteger, DateTime, Enum, String, Index

Base = declarative_base()

class AvwapAnchors(Base):
    __tablename__ = "avwap_anchors"
    anchor_id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id = Column(BigInteger, nullable=False)
    candle_width = Column(Enum("1d", "30m", "5m", "1m", name="cw_enum"), nullable=False)
    anchor_ts_utc = Column(DateTime(timezone=False), nullable=False)
    anchor_type = Column(Enum("session_open","weekly_open","monthly_open","swing_high","swing_low","custom_event", name="anchor_type_enum"), nullable=False)
    anchor_label = Column(String(64))
    created_utc = Column(DateTime(timezone=False), nullable=False)

    __table_args__ = (
        Index("idx_anchor_lookup", "symbol_id", "candle_width", "anchor_ts_utc"),
    )
