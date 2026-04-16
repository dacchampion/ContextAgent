"""add_gex_snapshots_table

Revision ID: 5f6c4c8d8f61
Revises: 481d9f3049ca
Create Date: 2026-03-31 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f6c4c8d8f61"
down_revision: Union[str, Sequence[str], None] = "481d9f3049ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "gex_snapshots"):
        return

    op.create_table(
        "gex_snapshots",
        sa.Column("snapshot_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.BigInteger(), sa.ForeignKey("symbols.symbol_id"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="options_data"),
        sa.Column("snapshot_utc", sa.DateTime(), nullable=False, server_default=sa.text("UTC_TIMESTAMP(3)")),
        sa.Column("zero_gamma_level", sa.Numeric(18, 6), nullable=True),
        sa.Column("dealer_cluster_upper", sa.Numeric(18, 6), nullable=True),
        sa.Column("dealer_cluster_lower", sa.Numeric(18, 6), nullable=True),
        sa.Column("dealer_cluster_upper_range_start", sa.Numeric(18, 6), nullable=True),
        sa.Column("dealer_cluster_lower_range_start", sa.Numeric(18, 6), nullable=True),
        sa.Column("gex_map", sa.JSON(), nullable=False),
        sa.Column("created_utc", sa.DateTime(), nullable=False, server_default=sa.text("UTC_TIMESTAMP(3)")),
    )
    op.create_index("idx_gex_snapshots_lookup", "gex_snapshots", ["symbol_id", "snapshot_utc"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "gex_snapshots"):
        return
    op.drop_index("idx_gex_snapshots_lookup", table_name="gex_snapshots")
    op.drop_table("gex_snapshots")
