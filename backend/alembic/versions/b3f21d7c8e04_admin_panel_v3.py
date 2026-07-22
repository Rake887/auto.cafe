"""admin panel v3: zones, honest dish tags, cost price, schedule, reviews

Revision ID: b3f21d7c8e04
Revises: a1c7e93b40d2
Create Date: 2026-07-22 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3f21d7c8e04'
down_revision: Union[str, None] = 'a1c7e93b40d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- зоны -------------------------------------------------------------
    op.create_table(
        'zone',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('order_counter', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('counter_day', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branch.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # У каждого филиала должна быть зона, иначе столам некуда встать.
    # Сначала колонка nullable, затем засев, и только потом NOT NULL.
    op.add_column('point', sa.Column('zone_id', sa.Integer(), nullable=True))
    op.execute(
        """
        INSERT INTO zone (branch_id, name, sort_order, order_counter)
        SELECT id, 'Основной зал', 0, 0 FROM branch
        """
    )
    op.execute(
        """
        UPDATE point SET zone_id = zone.id
        FROM zone WHERE zone.branch_id = point.branch_id
        """
    )
    op.alter_column('point', 'zone_id', nullable=False)
    op.create_foreign_key('point_zone_id_fkey', 'point', 'zone', ['zone_id'], ['id'])

    # Прошлые заказы остаются без зоны: сквозной номер у них уже напечатан
    # в чате, и задним числом переименовывать их незачем.
    op.add_column('orders', sa.Column('zone_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('zone_seq', sa.Integer(), nullable=True))
    op.create_foreign_key('orders_zone_id_fkey', 'orders', 'zone', ['zone_id'], ['id'])

    # --- метки блюда, аллергены, себестоимость ----------------------------
    for flag in ('is_veg', 'is_spicy', 'is_hit', 'is_chef'):
        op.add_column(
            'dish',
            sa.Column(flag, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column('dish', flag, server_default=None)
    op.add_column('dish', sa.Column('allergens', sa.String(length=300), nullable=True))
    op.add_column('dish', sa.Column('cost_price', sa.Integer(), nullable=True))
    op.add_column('order_item', sa.Column('cost_snapshot', sa.Integer(), nullable=True))

    # --- часы показа категории -------------------------------------------
    op.add_column('category', sa.Column('available_from', sa.Time(), nullable=True))
    op.add_column('category', sa.Column('available_to', sa.Time(), nullable=True))

    # --- дисклеймер и ссылка на отзывы ------------------------------------
    op.add_column('branch', sa.Column('menu_disclaimer', sa.String(length=1000), nullable=True))
    op.add_column('branch', sa.Column('review_url', sa.String(length=500), nullable=True))

    # --- эскалация вызовов и отзывы ---------------------------------------
    op.add_column(
        'service_call',
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.String(length=1000), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branch.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
        # одна оценка на заказ: иначе выставленную звезду можно переписать
        sa.UniqueConstraint('order_id'),
    )


def downgrade() -> None:
    op.drop_table('review')
    op.drop_column('service_call', 'escalated_at')

    op.drop_column('branch', 'review_url')
    op.drop_column('branch', 'menu_disclaimer')

    op.drop_column('category', 'available_to')
    op.drop_column('category', 'available_from')

    op.drop_column('order_item', 'cost_snapshot')
    op.drop_column('dish', 'cost_price')
    op.drop_column('dish', 'allergens')
    for flag in ('is_chef', 'is_hit', 'is_spicy', 'is_veg'):
        op.drop_column('dish', flag)

    op.drop_constraint('orders_zone_id_fkey', 'orders', type_='foreignkey')
    op.drop_column('orders', 'zone_seq')
    op.drop_column('orders', 'zone_id')

    op.drop_constraint('point_zone_id_fkey', 'point', type_='foreignkey')
    op.drop_column('point', 'zone_id')
    op.drop_table('zone')
