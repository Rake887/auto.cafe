"""launch ready: opening hours, stop switch, geo flag, table visits, kk menu

Revision ID: c5d84a1f2b70
Revises: b3f21d7c8e04
Create Date: 2026-07-22 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d84a1f2b70'
down_revision: Union[str, None] = 'b3f21d7c8e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- часы работы, стоп-кран, координаты зала ---------------------------
    op.add_column('branch', sa.Column('opens_at', sa.Time(), nullable=True))
    op.add_column('branch', sa.Column('closes_at', sa.Time(), nullable=True))
    op.add_column(
        'branch',
        sa.Column(
            'accepting_orders', sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.alter_column('branch', 'accepting_orders', server_default=None)
    op.add_column('branch', sa.Column('lat', sa.Numeric(9, 6), nullable=True))
    op.add_column('branch', sa.Column('lon', sa.Numeric(9, 6), nullable=True))
    op.add_column('branch', sa.Column('geo_radius_m', sa.Integer(), nullable=True))

    # --- визит стола -------------------------------------------------------
    op.create_table(
        'table_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('point_id', sa.Integer(), nullable=False),
        sa.Column(
            'opened_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branch.id']),
        sa.ForeignKeyConstraint(['point_id'], ['point.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_table_session_point_id', 'table_session', ['point_id'])

    # Прошлые заказы визита не знают: счёт по ним давно закрыт наличными.
    op.add_column('orders', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'orders_session_id_fkey', 'orders', 'table_session', ['session_id'], ['id']
    )
    op.add_column(
        'orders',
        sa.Column('is_remote', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('orders', 'is_remote', server_default=None)

    # --- казахские названия ------------------------------------------------
    op.add_column('category', sa.Column('name_kk', sa.String(length=255), nullable=True))
    op.add_column('dish', sa.Column('name_kk', sa.String(length=255), nullable=True))
    op.add_column(
        'dish', sa.Column('description_kk', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('dish', 'description_kk')
    op.drop_column('dish', 'name_kk')
    op.drop_column('category', 'name_kk')

    op.drop_column('orders', 'is_remote')
    op.drop_constraint('orders_session_id_fkey', 'orders', type_='foreignkey')
    op.drop_column('orders', 'session_id')

    op.drop_index('ix_table_session_point_id', table_name='table_session')
    op.drop_table('table_session')

    op.drop_column('branch', 'geo_radius_m')
    op.drop_column('branch', 'lon')
    op.drop_column('branch', 'lat')
    op.drop_column('branch', 'accepting_orders')
    op.drop_column('branch', 'closes_at')
    op.drop_column('branch', 'opens_at')
