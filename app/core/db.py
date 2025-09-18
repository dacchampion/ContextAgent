from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

from app.core.config import settings

# Usa la propiedad calculada, que respeta tu .env por componentes o DATABASE_URL si existe
engine = create_engine(
    settings.sqlalchemy_database_uri,
    echo=getattr(settings, "DEBUG_SQL", False),
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
