import base64, json
from typing import Optional

from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.api.deps import DBSessionDep
from app.core.security import require_api_key
from app.models.symbol import Symbol
from app.schemas.symbol import SymbolsResponse, SymbolOut

router = APIRouter(
    prefix="/symbols",
    tags=["symbols"],
    dependencies=[Depends(require_api_key)],
)

def _enc(last_id: int | None) -> str | None:
    if last_id is None:
        return None
    return base64.urlsafe_b64encode(json.dumps({"last": last_id}).encode()).decode()

def _dec(cursor: Optional[str]) -> Optional[int]:
    if not cursor:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return int(data.get("last"))
    except Exception:
        return None

@router.get("/", response_model=SymbolsResponse)
def list_symbols(
    db: DBSessionDep,
    q: str | None = Query(default=None, description="Buscar por prefijo de ticker o nombre"),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None, description="Cursor opaco de la página previa"),
):
    last_id = _dec(cursor)

    stmt = select(Symbol)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            func.lower(Symbol.symbol).like(func.lower(f"{q}%")),
            func.lower(Symbol.description).like(func.lower(like)),
        )
    )
    if last_id is not None:
        stmt = stmt.where(Symbol.symbol_id > last_id)
    stmt = stmt.order_by(Symbol.symbol_id.asc()).limit(limit + 1)

    rows = db.execute(stmt).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _enc(items[-1].symbol_id) if has_more else None

    # convertir ORM → Pydantic usando from_attributes
    items_out = [SymbolOut.model_validate(r) for r in items]

    return SymbolsResponse(data=items_out, next_cursor=next_cursor, limit=limit)
