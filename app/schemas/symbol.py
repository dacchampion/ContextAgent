from typing import Optional
from pydantic import BaseModel, ConfigDict

class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # <- clave en Pydantic v2

    symbol_id: int
    symbol: str
    asset_class: str
    exchange: Optional[str] = None
    description: Optional[str] = None

class SymbolsResponse(BaseModel):
    # no es obligatorio aquí, pero no estorba:
    model_config = ConfigDict(from_attributes=True)
    data: list[SymbolOut]
    next_cursor: str | None = None
    limit: int
