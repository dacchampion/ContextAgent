"""add bollinger columns to indicators

Revision ID: 9f7407374454
Revises: e0056e95f626
Create Date: 2025-09-18 18:02:25.651559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f7407374454'
down_revision: Union[str, Sequence[str], None] = 'e0056e95f626'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table_name: str, col_name: str) -> bool:
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return col_name in cols


def _has_index(bind, table_name: str, index_name: str) -> bool:
    insp = sa.inspect(bind)
    idxs = insp.get_indexes(table_name)
    names = {i.get("name") for i in idxs if i.get("name")}
    return index_name in names


def upgrade():
    bind = op.get_bind()

    # ---- Columnas Bollinger (NULLables por warmup) ----
    for col_name in ["bb_mid", "bb_up", "bb_dn", "bb_percB", "bb_bw"]:
        if not _has_column(bind, "indicators", col_name):
            op.add_column(
                "indicators",
                sa.Column(col_name, sa.Float(), nullable=True)
            )

    # ---- Índice de lectura (no único) ----
    if not _has_index(bind, "indicators", "ind_sid_cw_ts"):
        op.create_index(
            "ind_sid_cw_ts",
            "indicators",
            ["symbol_id", "candle_width", "timestamp_utc"],
            unique=False,
        )

    # ---- Unique para ON DUPLICATE KEY ----
    # Si ya tienes un unique equivalente, puedes omitir esto.
    # Alembic normaliza a índice único en MySQL.
    if not _has_index(bind, "indicators", "uniq_sid_cw_ts"):
        op.create_index(
            "uniq_sid_cw_ts",
            "indicators",
            ["symbol_id", "candle_width", "timestamp_utc"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()

    # Drop unique/index si los creamos aquí
    if _has_index(bind, "indicators", "uniq_sid_cw_ts"):
        op.drop_index("uniq_sid_cw_ts", table_name="indicators")

    if _has_index(bind, "indicators", "ind_sid_cw_ts"):
        op.drop_index("ind_sid_cw_ts", table_name="indicators")

    # Quitar columnas BB si existen
    for col_name in ["bb_bw", "bb_percB", "bb_dn", "bb_up", "bb_mid"]:
        if _has_column(bind, "indicators", col_name):
            op.drop_column("indicators", col_name)
