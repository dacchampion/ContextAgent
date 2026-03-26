"""add_keltner_channel_columns_to_indicators

Revision ID: a065491598f7
Revises: 9f7407374454
Create Date: 2026-03-24 20:06:03.459901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a065491598f7'
down_revision: Union[str, Sequence[str], None] = '9f7407374454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table_name: str, col_name: str) -> bool:
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return col_name in cols


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    for col_name in ["kc_mid", "kc_up", "kc_dn"]:
        if not _has_column(bind, "indicators", col_name):
            op.add_column(
                "indicators",
                sa.Column(col_name, sa.Float(), nullable=True)
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    for col_name in ["kc_dn", "kc_up", "kc_mid"]:
        if _has_column(bind, "indicators", col_name):
            op.drop_column("indicators", col_name)
