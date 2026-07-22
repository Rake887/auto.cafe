"""admin panel v2: staff hiring state and archived tables

Revision ID: a1c7e93b40d2
Revises: 7997f34d84b2
Create Date: 2026-07-22 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c7e93b40d2'
down_revision: Union[str, None] = '7997f34d84b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default нужен только на время миграции: у существующих строк
    # значения взяться неоткуда, а колонки должны быть NOT NULL
    op.add_column(
        'staff',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'point',
        sa.Column(
            'is_archived', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column('staff', 'is_active', server_default=None)
    op.alter_column('point', 'is_archived', server_default=None)


def downgrade() -> None:
    op.drop_column('point', 'is_archived')
    op.drop_column('staff', 'is_active')
