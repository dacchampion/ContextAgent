# backend/tools/smoke_context.py
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

# --- Asegura que 'app' y 'services' sean importables (añade <repo>/backend al sys.path)
THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = THIS_FILE.parents[1]  # .../<repo>/backend
sys.path.insert(0, str(BACKEND_DIR))

# --- Importa la sesión vía dependencia real
from app.api.deps import get_db  # <-- la fuente de verdad

# --- Importa el builder (según tu import actual en el router)
try:
    from services.context_builder import build_context_json
except ModuleNotFoundError:
    # fallback si lo importas con namespace "backend.services"
    from backend.services.context_builder import build_context_json  # type: ignore


@contextmanager
def db_session_from_dep():
    """
    Usa el generador get_db() de FastAPI fuera del request cycle.
    Respeta el teardown de la dependencia.
    """
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            # dispara el 'finally' interno de get_db() para cerrar la sesión
            next(gen)
        except StopIteration:
            pass


def main():
    symbol = os.getenv("SMOKE_SYMBOL", "AAPL")
    tfs = os.getenv("SMOKE_TFS", "1D,30m,5m").split(",")
    with db_session_from_dep() as db:
        out = build_context_json(db, symbol, tfs)
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
