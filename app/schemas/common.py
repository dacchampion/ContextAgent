from pydantic import BaseModel

class CursorPage(BaseModel):
    next_cursor: str | None = None
    limit: int
    