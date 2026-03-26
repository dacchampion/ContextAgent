"""increase_indicator_method_length

Revision ID: 481d9f3049ca
Revises: a065491598f7
Create Date: 2026-03-24 21:17:32.441896

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '481d9f3049ca'
down_revision: Union[str, Sequence[str], None] = 'a065491598f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'indicator_series',
        'indicator_method',
        type_=sa.String(64),
        existing_type=sa.String(24),
        nullable=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'indicator_series',
        'indicator_method',
        type_=sa.String(24),
        existing_type=sa.String(64),
        nullable=True
    )
