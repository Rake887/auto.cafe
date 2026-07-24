"""Подсчёт статистики для страницы администратора.

Всё считается в SQL: строк заказов может быть много, тащить их в приложение
ради суммирования незачем.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Branch,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusLog,
    Review,
    StaffRole,
    Zone,
)
from app.core.config import Settings, get_settings
from app.services.orders import LINE_TOTAL, SOLD_ITEM
from app.services.staff_lookup import staff_by_telegram
from app.schemas.admin import (
    AdminStats,
    BucketOut,
    DishStatOut,
    StaffStatOut,
    TotalsOut,
    ZoneStatOut,
)

# Периоды без привязки к часовому поясу: «за последние N часов»
PERIODS: dict[str, timedelta | None] = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "all": None,
}

PERIOD_TITLES = {"day": "За сутки", "week": "За неделю", "all": "За всё время"}

ROLE_TITLES = {"cook": "повар", "waiter": "официант"}


def period_start(period: str) -> datetime | None:
    """Начало периода; None — «за всё время», ограничения по дате нет."""
    delta = PERIODS.get(period)
    return datetime.now(UTC) - delta if delta else None


def _in_period(stmt: Select, since: datetime | None) -> Select:
    return stmt.where(Order.created_at >= since) if since else stmt


async def collect_stats(
    session: AsyncSession, branch_id: int, period: str
) -> AdminStats:
    settings = get_settings()
    since = period_start(period)
    branch_name = await session.scalar(
        select(Branch.name).where(Branch.id == branch_id)
    )

    paid = Order.status != OrderStatus.cancelled
    # сумма заказа = сумма его позиций по ценам на момент заказа, за вычетом
    # того, что кухня не смогла отдать (LINE_TOTAL обнуляет такие позиции)
    line_total = LINE_TOTAL

    revenue, orders_count = (
        await session.execute(
            _in_period(
                select(
                    func.coalesce(func.sum(case((paid, line_total), else_=0)), 0),
                    func.count(func.distinct(case((paid, Order.id)))),
                )
                .select_from(Order)
                .join(OrderItem, OrderItem.order_id == Order.id)
                .where(Order.branch_id == branch_id),
                since,
            )
        )
    ).one()

    in_progress, cancelled, untouched = (
        await session.execute(
            _in_period(
                select(
                    func.count().filter(
                        Order.status.in_(
                            [OrderStatus.new, OrderStatus.accepted, OrderStatus.ready]
                        )
                    ),
                    func.count().filter(Order.status == OrderStatus.cancelled),
                    func.count().filter(Order.status == OrderStatus.new),
                ).where(Order.branch_id == branch_id),
                since,
            )
        )
    ).one()

    # деньги в заказах, которых никто не взял в работу
    untouched_revenue = await session.scalar(
        _in_period(
            select(func.coalesce(func.sum(line_total), 0))
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(Order.branch_id == branch_id, Order.status == OrderStatus.new),
            since,
        )
    )

    # среднее время «оформлен -> отдан гостю»
    served_at = (
        select(
            OrderStatusLog.order_id.label("order_id"),
            func.min(OrderStatusLog.at).label("at"),
        )
        .where(OrderStatusLog.to_status == OrderStatus.served)
        .group_by(OrderStatusLog.order_id)
        .subquery()
    )
    avg_seconds = await session.scalar(
        _in_period(
            select(
                func.avg(
                    func.extract("epoch", served_at.c.at - Order.created_at)
                )
            )
            .select_from(Order)
            .join(served_at, served_at.c.order_id == Order.id)
            .where(Order.branch_id == branch_id),
            since,
        )
    )

    # Прибыль считаем только там, где на момент заказа знали себестоимость.
    # Позиции без неё дали бы прибыль, равную всей цене, — это была бы ложь.
    known_cost = OrderItem.cost_snapshot.is_not(None)
    line_profit = (OrderItem.price_snapshot - OrderItem.cost_snapshot) * OrderItem.qty
    line_cost = OrderItem.cost_snapshot * OrderItem.qty

    top_dishes = (
        await session.execute(
            _in_period(
                select(
                    OrderItem.dish_name_snapshot,
                    func.sum(OrderItem.qty),
                    func.sum(line_total),
                    func.sum(case((known_cost, line_profit), else_=None)),
                )
                .select_from(OrderItem)
                .join(Order, Order.id == OrderItem.order_id)
                # непроданное в топ блюд не идёт: гость его не получил
                .where(Order.branch_id == branch_id, paid, SOLD_ITEM)
                .group_by(OrderItem.dish_name_snapshot)
                .order_by(func.sum(OrderItem.qty).desc())
                .limit(10),
                since,
            )
        )
    ).all()

    # Выручка и себестоимость по тем позициям, где себестоимость известна:
    # делить одно на другое можно только внутри одной и той же выборки
    costed_revenue, costed_cost, costed_qty, total_qty = (
        await session.execute(
            _in_period(
                select(
                    func.coalesce(
                        func.sum(case((known_cost, line_total), else_=0)), 0
                    ),
                    func.coalesce(
                        func.sum(case((known_cost, line_cost), else_=0)), 0
                    ),
                    func.coalesce(
                        func.sum(case((known_cost, OrderItem.qty), else_=0)), 0
                    ),
                    func.coalesce(func.sum(OrderItem.qty), 0),
                )
                .select_from(OrderItem)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.branch_id == branch_id, paid, SOLD_ITEM),
                since,
            )
        )
    ).one()

    top_profit = (
        await session.execute(
            _in_period(
                select(
                    OrderItem.dish_name_snapshot,
                    func.sum(OrderItem.qty),
                    func.sum(line_total),
                    func.sum(line_profit),
                )
                .select_from(OrderItem)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.branch_id == branch_id, paid, known_cost, SOLD_ITEM)
                .group_by(OrderItem.dish_name_snapshot)
                .order_by(func.sum(line_profit).desc())
                .limit(10),
                since,
            )
        )
    ).all()

    # средняя оценка за период: считается по отзывам, а не по заказам
    rating_avg, rating_count = (
        await session.execute(
            (
                select(func.avg(Review.rating), func.count())
                .select_from(Review)
                .where(Review.branch_id == branch_id, Review.created_at >= since)
                if since
                else select(func.avg(Review.rating), func.count())
                .select_from(Review)
                .where(Review.branch_id == branch_id)
            )
        )
    ).one()

    return AdminStats(
        period=period,
        branch_name=branch_name or "",
        totals=TotalsOut(
            orders=orders_count,
            revenue=int(revenue),
            average_check=int(revenue / orders_count) if orders_count else 0,
            in_progress=in_progress,
            cancelled=cancelled,
            untouched=untouched,
            untouched_revenue=int(untouched_revenue or 0),
            avg_minutes_to_served=(
                round(float(avg_seconds) / 60, 1) if avg_seconds is not None else None
            ),
            food_cost_percent=(
                round(int(costed_cost) / int(costed_revenue) * 100, 1)
                if costed_revenue
                else None
            ),
            profit=int(costed_revenue) - int(costed_cost) if costed_revenue else 0,
            # доля порций, у которых себестоимость известна: по неполным данным
            # процент фудкоста нельзя показывать как точный
            costed_share=(
                round(int(costed_qty) / int(total_qty) * 100)
                if total_qty
                else 0
            ),
        ),
        top_dishes=[
            DishStatOut(
                name=name,
                qty=int(qty),
                revenue=int(rev),
                profit=int(profit) if profit is not None else None,
            )
            for name, qty, rev, profit in top_dishes
        ],
        top_profit=[
            DishStatOut(
                name=name, qty=int(qty), revenue=int(rev), profit=int(profit)
            )
            for name, qty, rev, profit in top_profit
        ],
        by_hour=await _buckets(session, branch_id, since, "hour", settings),
        by_weekday=await _buckets(session, branch_id, since, "dow", settings),
        by_zone=await _zone_stats(session, branch_id, since),
        rating_avg=round(float(rating_avg), 1) if rating_avg is not None else None,
        rating_count=rating_count,
        waiters=await _staff_stats(
            session, branch_id, since, OrderStatus.served, StaffRole.waiter
        ),
        cooks=await _staff_stats(
            session, branch_id, since, OrderStatus.accepted, StaffRole.cook
        ),
    )


WEEKDAYS = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]


async def _buckets(
    session: AsyncSession,
    branch_id: int,
    since: datetime | None,
    unit: str,
    settings: Settings,
) -> list[BucketOut]:
    """Заказы и выручка по часам суток или дням недели.

    Время приводим к часовому поясу заведения: в базе оно в UTC, а владельцу
    нужен его собственный вечерний час пик, а не сдвинутый на пять часов.
    """
    local_time = func.timezone(settings.display_timezone, Order.created_at)
    bucket = func.date_part(unit, local_time)
    line_total = LINE_TOTAL

    rows = (
        await session.execute(
            _in_period(
                select(
                    bucket,
                    func.count(func.distinct(Order.id)),
                    func.coalesce(func.sum(line_total), 0),
                )
                .select_from(Order)
                .join(OrderItem, OrderItem.order_id == Order.id)
                .where(
                    Order.branch_id == branch_id,
                    Order.status != OrderStatus.cancelled,
                )
                .group_by(bucket)
                .order_by(bucket),
                since,
            )
        )
    ).all()

    return [
        BucketOut(
            label=(
                f"{int(value):02d}:00" if unit == "hour" else WEEKDAYS[int(value)]
            ),
            orders=count,
            revenue=int(revenue),
        )
        for value, count, revenue in rows
    ]


async def _zone_stats(
    session: AsyncSession, branch_id: int, since: datetime | None
) -> list[ZoneStatOut]:
    """Выручка и средний чек по залам. Заказы до появления зон пропускаем."""
    line_total = LINE_TOTAL
    rows = (
        await session.execute(
            _in_period(
                select(
                    Zone.name,
                    func.count(func.distinct(Order.id)),
                    func.coalesce(func.sum(line_total), 0),
                )
                .select_from(Order)
                .join(Zone, Zone.id == Order.zone_id)
                .join(OrderItem, OrderItem.order_id == Order.id)
                .where(
                    Order.branch_id == branch_id,
                    Order.status != OrderStatus.cancelled,
                )
                .group_by(Zone.name)
                .order_by(func.coalesce(func.sum(line_total), 0).desc()),
                since,
            )
        )
    ).all()
    return [
        ZoneStatOut(
            name=name,
            orders=count,
            revenue=int(revenue),
            average_check=int(int(revenue) / count) if count else 0,
        )
        for name, count, revenue in rows
    ]


async def _staff_stats(
    session: AsyncSession,
    branch_id: int,
    since: datetime | None,
    to_status: OrderStatus,
    expected_role: StaffRole,
) -> list[StaffStatOut]:
    """Кто сколько заказов перевёл в нужный статус и на какую сумму.

    Группируем по telegram-id нажавшего: имя и роль подтягиваем из staff,
    а если человек не зарегистрирован — показываем сам id.
    """
    line_total = LINE_TOTAL
    rows = (
        await session.execute(
            _in_period(
                select(
                    OrderStatusLog.actor_telegram_id,
                    func.count(func.distinct(Order.id)),
                    func.coalesce(func.sum(line_total), 0),
                )
                .select_from(OrderStatusLog)
                .join(Order, Order.id == OrderStatusLog.order_id)
                .join(OrderItem, OrderItem.order_id == Order.id)
                .where(
                    Order.branch_id == branch_id,
                    OrderStatusLog.to_status == to_status,
                    OrderStatusLog.actor_telegram_id.is_not(None),
                )
                .group_by(OrderStatusLog.actor_telegram_id)
                .order_by(func.count(func.distinct(Order.id)).desc()),
                since,
            )
        )
    ).all()
    if not rows:
        return []

    by_chat = await staff_by_telegram(
        session, [r[0] for r in rows], branch_id, expected_role
    )

    result = []
    for chat_id, count, revenue in rows:
        staff = by_chat.get(chat_id)
        result.append(
            StaffStatOut(
                name=staff.full_name if staff else f"ID {chat_id}",
                role=ROLE_TITLES.get(staff.role.value) if staff else None,
                orders=count,
                revenue=int(revenue),
            )
        )
    return result
