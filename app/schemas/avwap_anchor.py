# app/schemas/avwap_anchor.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import BaseModel, ConfigDict, Field

CandleWidthLit = Literal["1d", "30m", "5m", "1m"]
AnchorTypeLit = Literal["session_open","weekly_open","monthly_open","swing_high","swing_low","custom_event"]

class AnchorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    anchor_id: int
    symbol_id: int
    candle_width: CandleWidthLit
    anchor_type: AnchorTypeLit
    anchor_ms: int = Field(..., description="Epoch ms (UTC)")
    anchor_label: Optional[str] = None
    created_ms: int

class AnchorCreate(BaseModel):
    symbol_id: int
    candle_width: CandleWidthLit
    anchor_type: AnchorTypeLit
    anchor_ms: int
    anchor_label: Optional[str] = None

class AnchorUpdate(BaseModel):
    anchor_ms: Optional[int] = None
    anchor_type: Optional[AnchorTypeLit] = None
    anchor_label: Optional[str] = None

class AnchorsResponse(BaseModel):
    data: List[AnchorOut]
    next_cursor: str | None = None
    limit: int
