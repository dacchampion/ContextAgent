# app/schemas/indicators.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer

CandleWidthLit = Literal["1d", "30m", "5m", "1m"]

class IndicatorsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol_id: int
    candle_width: CandleWidthLit
    timestamp_ms: int = Field(..., description="Epoch ms (UTC)")

    vwap: Optional[Decimal] = None
    ema8: Optional[Decimal] = None
    ema21: Optional[Decimal] = None
    ema50: Optional[Decimal] = None
    sma20: Optional[Decimal] = None
    sma50: Optional[Decimal] = None

    updated_ms: int

    @field_serializer("vwap","ema8","ema21","ema50","sma20","sma50")
    def _ser_decimal(self, v: Optional[Decimal], _):
        return float(v) if v is not None else None

class IndicatorsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: list[IndicatorsRow]
    next_cursor: str | None = None
    limit: int
