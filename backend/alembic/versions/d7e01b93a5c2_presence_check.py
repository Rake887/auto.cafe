"""presence check: trusted cafe IP and confirmed table visits

Revision ID: d7e01b93a5c2
Revises: c5d84a1f2b70
Create Date: 2026-07-22 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7e01b93a5c2'
down_revision: Union[str, None] = 'c5d84a1f2b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IPv6 в текстовом виде — до 45 символов
    op.add_column('branch', sa.Column('trusted_ip', sa.String(length=45), nullable=True))
    op.add_column(
        'table_session',
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Визиты, заведённые до появления проверки, считаем подтверждёнными:
    # иначе открытые счета внезапно потребовали бы подтверждения задним числом.
    op.execute("UPDATE table_session SET confirmed_at = opened_at")


def downgrade() -> None:
    op.drop_column('table_session', 'confirmed_at')
    op.drop_column('branch', 'trusted_ip')
