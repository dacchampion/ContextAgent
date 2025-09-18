# app/api/deps.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import require_api_key

DBSessionDep = Annotated[Session, Depends(get_db)]
APIKeyDep = Annotated[None, Depends(require_api_key)]
