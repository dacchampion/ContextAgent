"""init schema

Revision ID: e0056e95f626
Revises: 
Create Date: 2025-08-30 20:35:00.018961

"""
from typing import Sequence, Union

from alembic import op
from pathlib import Path
import sqlalchemy as sa
import os
import re

# revision identifiers, used by Alembic.
revision: str = 'e0056e95f626'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_and_clean_sql(path: str) -> str:
    raw = Path(path).read_text(encoding="utf-8")

    # quitar bloques /* ... */
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)

    # quitar líneas -- comentario
    lines = []
    for line in raw.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    # quitar CREATE DATABASE y USE ...
    cleaned = re.sub(r"(?im)^\s*CREATE\s+DATABASE\b.*?;\s*", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*USE\s+[`\"\w-]+\s*;\s*", "", cleaned)

    return cleaned.strip()


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split por ';' sin romper strings.
    No soporta DELIMITER ni procedimientos complejos.
    """
    stmts = []
    buf = []
    in_str = False
    quote = None
    escape = False

    for ch in sql:
        if in_str:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
                quote = None
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                buf.append(ch)
            elif ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    stmts.append(stmt)
                buf = []
            else:
                buf.append(ch)

    rest = "".join(buf).strip()
    if rest:
        stmts.append(rest)

    # filtrar vacíos por si acaso
    return [s for s in stmts if s.strip()]

def upgrade():
    # Lee y ejecuta tu SQL (ruta relativa desde la raíz del backend)
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.sql")
    schema_path = os.path.abspath(schema_path)

    print(schema_path)
    sql = _load_and_clean_sql(schema_path)
    statements = _split_sql_statements(sql)
    print(len(statements))

    conn = op.get_bind()

    # Forzar InnoDB/FKs coherentes (depende de tu caso, puedes dejarlo en 1)
    conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")

    for i, stmt in enumerate(statements, 1):
        try:
            print(f"[alembic] executing {i}/{len(statements)}: {stmt[:80]}...")
            conn.exec_driver_sql(stmt)
        except Exception as e:
            print(f"[alembic] ERROR on statement {i}: {e}\nSQL was:\n{stmt}\n")
            raise 


def downgrade():
    conn = op.get_bind()

    stmts = [
        # 1) Vistas primero
        "DROP VIEW IF EXISTS v_indicator_series",
        "DROP VIEW IF EXISTS v_last_bars_core",

        # 2) Desactivar FKs para evitar orden estricto
        "SET FOREIGN_KEY_CHECKS = 0",

        # 3) Tablas en orden de dependencias (hijas -> padres)
        "DROP TABLE IF EXISTS job_runs",
        "DROP TABLE IF EXISTS sync_meta",
        "DROP TABLE IF EXISTS avwap_anchors",
        "DROP TABLE IF EXISTS indicator_series",
        "DROP TABLE IF EXISTS indicators",
        "DROP TABLE IF EXISTS ohlcv",
        "DROP TABLE IF EXISTS providers",
        "DROP TABLE IF EXISTS symbols",

        # 4) Reactivar FKs
        "SET FOREIGN_KEY_CHECKS = 1",
    ]

    for s in stmts:
        conn.exec_driver_sql(s)
