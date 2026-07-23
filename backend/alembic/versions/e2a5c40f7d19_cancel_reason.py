"""cancel reason and cancelling a ready order

Revision ID: e2a5c40f7d19
Revises: d7e01b93a5c2
Create Date: 2026-07-22 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a5c40f7d19'
down_revision: Union[str, None] = 'd7e01b93a5c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'orders', sa.Column('cancel_reason', sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('orders', 'cancel_reason')
