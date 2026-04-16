# app/models/gex_snapshot.py
from __future__ import annotations

from app.models.base import Base
from sqlalchemy import BigInteger, Column, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime
from sqlalchemy.types import JSON


class GexSnapshot(Base):
    __tablename__ = "gex_snapshots"

    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id = Column(BigInteger, ForeignKey("symbols.symbol_id"), nullable=False, index=True)
    source = Column(String(32), nullable=False, default="options_data")
    snapshot_utc = Column(MySQLDateTime(fsp=3), nullable=False, index=True)
    zero_gamma_level = Column(Numeric(18, 6), nullable=True)
    dealer_cluster_upper = Column(Numeric(18, 6), nullable=True)
    dealer_cluster_lower = Column(Numeric(18, 6), nullable=True)
    dealer_cluster_upper_range_start = Column(Numeric(18, 6), nullable=True)
    dealer_cluster_lower_range_start = Column(Numeric(18, 6), nullable=True)
    gex_map = Column(JSON, nullable=False)
    created_utc = Column(MySQLDateTime(fsp=3), nullable=False)

    __table_args__ = (
        Index("idx_gex_snapshots_lookup", "symbol_id", "snapshot_utc"),
    )
