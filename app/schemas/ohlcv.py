# app/schemas/ohlcv.py
from __future__ import annotations
from typing import Optional, Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_serializer

CandleWidthLit = Literal["1d", "30m", "5m", "1m"]

class OhlcvOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol_id: int
    candle_width: CandleWidthLit
    # timestamp en milisegundos UTC para el frontend (más práctico)
    timestamp_ms: int = Field(..., description="Epoch ms (UTC)")

    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Optional[Decimal] = None

    provider_id: int

    # Serializa Decimal -> float para JSON
    @field_serializer("open_price", "high_price", "low_price", "close_price", "volume")
    def _ser_decimal(self, v: Optional[Decimal], _info):
        return float(v) if v is not None else None

class OhlcvResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: list[OhlcvOut]
    next_cursor: str | None = None
    limit: int
