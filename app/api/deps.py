# app/api/deps.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import require_api_key
from app.services.narrator import NarratorService

DBSessionDep = Annotated[Session, Depends(get_db)]
APIKeyDep = Annotated[None, Depends(require_api_key)]

def get_narrator_service(db: DBSessionDep) -> NarratorService:
    return NarratorService(db)
