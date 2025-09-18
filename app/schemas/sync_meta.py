# app/schemas/sync_meta.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import BaseModel, ConfigDict, Field

CandleWidthLit = Literal["1d", "30m", "5m", "1m"]

class SyncMetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol_id: int
    candle_width: CandleWidthLit
    last_backfill_ms: Optional[int] = Field(None, description="Epoch ms UTC")
    last_realtime_ms: Optional[int] = Field(None, description="Epoch ms UTC")
    updated_ms: int

class SyncMetaUpdate(BaseModel):
    # cualquiera puede venir; si omites, no toca el valor actual
    last_backfill_ms: Optional[int] = None
    last_realtime_ms: Optional[int] = None

class SyncMetaListResponse(BaseModel):
    data: List[SyncMetaOut]
    next_cursor: str | None = None
    limit: int
