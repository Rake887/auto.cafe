"""order item marked as run out by the waiter

Revision ID: f6b21a4c8d37
Revises: e2a5c40f7d19
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b21a4c8d37'
down_revision: Union[str, None] = 'e2a5c40f7d19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'order_item',
        sa.Column('unavailable_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('order_item', 'unavailable_at')
