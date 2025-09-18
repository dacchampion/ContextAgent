# app/schemas/indicator_series.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import BaseModel, ConfigDict, Field, field_serializer

CandleWidthLit = Literal["1d", "30m", "5m", "1m"]

class IndicatorPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol_id: int
    candle_width: CandleWidthLit
    timestamp_ms: int
    indicator_name: str
    window_size: int
    indicator_value: Decimal
    indicator_method: Optional[str] = None

    @field_serializer("indicator_value")
    def _ser_decimal(self, v: Decimal, _):
        return float(v) if v is not None else None

class IndicatorSeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: List[IndicatorPointOut]
    next_cursor: str | None = None
    limit: int
