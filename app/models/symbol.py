# app/models/symbol.py
from sqlalchemy import Column, BigInteger, String, Enum
import enum
from app.models.base import Base

class AssetClassEnum(str, enum.Enum):
    equity = "equity"
    etf = "etf"
    index = "index"
    crypto = "crypto"
    fx = "fx"

class Symbol(Base):
    __tablename__ = "symbols"

    symbol_id   = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    symbol      = Column(String(32), unique=True, index=True, nullable=False)  # ticker real
    asset_class = Column(Enum(AssetClassEnum), nullable=False, default="equity")
    exchange    = Column(String(32), nullable=True)
    description = Column(String(255), nullable=True)
