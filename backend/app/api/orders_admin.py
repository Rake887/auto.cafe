"""Лента заказов в кабинете и отмена заказа.

Telegram-группа показывает заказы по одному и тонет в переписке; владельцу
нужен общий список за период — и возможность закрыть заказ, который в чате
никто не тронул.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_branch, require_admin
from app.core.db import get_session
from app.models import (
    Branch,
    Order,
    OrderStatus,
    OrderStatusLog,
    Point,
    StaffRole,
    Zone,
)
from app.schemas.admin import AdminOrderItemOut, AdminOrderOut
from app.services.orders import advance_order_status, order_label
from app.services import telegram_notify
from app.services.staff_lookup import staff_by_telegram
from app.services.stats import PERIODS, period_start

router = APIRouter(prefix="/admin", tags=["admin"])

# Роль, которую ожидаем увидеть за каждым переходом статуса
ACTOR_ROLES = {
    OrderStatus.accepted: StaffRole.cook,
    OrderStatus.served: StaffRole.waiter,
}


async def _actors(
    session: AsyncSession, order_ids: list[int], branch_id: int
) -> dict[tuple[int, OrderStatus], str]:
    """Имена исполнителей сразу по всей выборке заказов.

    Поштучный обход, как в гостевой ручке заказа, дал бы здесь N+1: на сотню
    заказов это сотни запросов ради двух имён на карточку.
    """
    if not order_ids:
        return {}

    rows = (
        await session.execute(
            select(
                OrderStatusLog.order_id,
                OrderStatusLog.to_status,
                OrderStatusLog.actor_telegram_id,
            )
            .where(
                OrderStatusLog.order_id.in_(order_ids),
                OrderStatusLog.to_status.in_(list(ACTOR_ROLES)),
                OrderStatusLog.actor_telegram_id.is_not(None),
            )
            .order_by(OrderStatusLog.id)
        )
    ).all()
    if not rows:
        return {}

    # по одному запросу на роль: один и тот же аккаунт может быть заведён
    # и поваром, и официантом, и выбрать нужную запись без роли нельзя
    by_role = {
        status: await staff_by_telegram(
            session,
            [r.actor_telegram_id for r in rows if r.to_status == status],
            branch_id,
            role,
        )
        for status, role in ACTOR_ROLES.items()
    }

    result: dict[tuple[int, OrderStatus], str] = {}
    for order_id, to_status, telegram_id in rows:
        staff = by_role[to_status].get(telegram_id)
        if staff is not None:
            result[(order_id, to_status)] = staff.full_name
    return result


@router.get("/orders", response_model=list[AdminOrderOut])
async def admin_orders(
    period: str = Query(default="day"),
    limit: int = Query(default=100, ge=1, le=500),
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Заказы за период, свежие сверху."""
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period: {', '.join(PERIODS)}")

    stmt = (
        select(Order, Point.label, Zone.name)
        .join(Point, Point.id == Order.point_id)
        # зону берём из снапшота заказа: стол мог с тех пор переехать
        .outerjoin(Zone, Zone.id == Order.zone_id)
        .where(Order.branch_id == branch.id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    since = period_start(period)
    if since is not None:
        stmt = stmt.where(Order.created_at >= since)

    rows = (await session.execute(stmt)).all()
    actors = await _actors(session, [o.id for o, _, _ in rows], branch.id)

    return [
        AdminOrderOut(
            id=order.id,
            number=order_label(order, zone_name),
            created_at=order.created_at,
            status=order.status,
            point_label=label,
            zone_name=zone_name,
            total=order.total,
            comment=order.comment,
            is_remote=order.is_remote,
            items=[
                AdminOrderItemOut(
                    name=i.dish_name_snapshot, qty=i.qty, price=i.price_snapshot
                )
                for i in order.items
            ],
            cooked_by=actors.get((order.id, OrderStatus.accepted)),
            served_by=actors.get((order.id, OrderStatus.served)),
        )
        for order, label, zone_name in rows
    ]


@router.post("/orders/{order_id}/cancel", response_model=AdminOrderOut)
async def cancel_order(
    order_id: int,
    actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Отменить заказ. Обслуженный отменить уже нельзя — еда на столе."""
    order = await session.get(Order, order_id)
    if order is None or order.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # переход проверяет и логирует сам сервис: из served и cancelled назад хода нет
    cancelled = await advance_order_status(
        session, order_id, OrderStatus.cancelled, None
    )
    if cancelled is None:
        raise HTTPException(
            status_code=409, detail="Этот заказ отменить уже нельзя"
        )

    point = await session.get_one(Point, cancelled.point_id)
    zone_name = await session.scalar(
        select(Zone.name).where(Zone.id == cancelled.zone_id)
    )
    if cancelled.tg_message_id is not None:
        await telegram_notify.edit_order_cancelled(
            cancelled.tg_message_id, cancelled, point, actor, zone_name
        )

    actors = await _actors(session, [cancelled.id], branch.id)
    return AdminOrderOut(
        id=cancelled.id,
        number=order_label(cancelled, zone_name),
        created_at=cancelled.created_at,
        status=cancelled.status,
        point_label=point.label,
        zone_name=zone_name,
        total=cancelled.total,
        comment=cancelled.comment,
        is_remote=cancelled.is_remote,
        items=[
            AdminOrderItemOut(
                name=i.dish_name_snapshot, qty=i.qty, price=i.price_snapshot
            )
            for i in cancelled.items
        ],
        cooked_by=actors.get((cancelled.id, OrderStatus.accepted)),
        served_by=actors.get((cancelled.id, OrderStatus.served)),
    )
