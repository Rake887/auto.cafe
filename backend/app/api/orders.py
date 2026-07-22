import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import (
    Order,
    OrderStatus,
    OrderStatusLog,
    Point,
    StaffRole,
    TableSession,
    Zone,
)
from app.schemas.orders import OrderCreate, OrderCreated, OrderItemOut, OrderOut
from app.services import telegram_notify
from app.services.orders import (
    DishesNotFound,
    OrdersNotAccepted,
    PointNotFound,
    TooManyOrders,
    client_ip,
    create_order,
    order_label,
    visit_totals,
)
from app.services.staff_lookup import staff_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreated, status_code=201)
async def place_order(
    body: OrderCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Оформить заказ. Идемпотентно по client_request_id — дубль не создаётся.

    Цены клиент не присылает: сервер сам берёт актуальные цены из БД и
    фиксирует их снапшотами в позициях заказа.
    """
    try:
        order, created = await create_order(
            session,
            point_token=body.point_token,
            client_request_id=body.client_request_id,
            items=[(i.dish_id, i.qty) for i in body.items],
            comment=body.comment,
            guest_lat=body.lat,
            guest_lon=body.lon,
            guest_ip=client_ip(
                request.headers.get("x-forwarded-for"),
                request.client.host if request.client else None,
            ),
        )
    except PointNotFound:
        raise HTTPException(status_code=404, detail="Стол с таким QR-кодом не найден")
    except OrdersNotAccepted as e:
        raise HTTPException(status_code=409, detail=e.reason) from None
    except TooManyOrders:
        raise HTTPException(
            status_code=429,
            detail="Слишком много заказов с этого стола подряд. Подождите немного "
            "или позовите официанта.",
        ) from None
    except DishesNotFound as e:
        raise HTTPException(
            status_code=422,
            detail=f"Блюда недоступны или не найдены: {e.dish_ids}",
        )

    if created:
        point = await session.get_one(Point, order.point_id)
        zone_name = await session.scalar(
            select(Zone.name).where(Zone.id == point.zone_id)
        )
        visit_orders, visit_total = await visit_totals(session, order.session_id)
        visit = (
            await session.get(TableSession, order.session_id)
            if order.session_id
            else None
        )
        message_id = await telegram_notify.notify_new_order(
            order,
            point,
            zone_name,
            visit_orders,
            visit_total,
            # пока за стол никто не поручился, кухне нельзя давать «Принял»
            needs_presence=visit is not None and visit.confirmed_at is None,
        )
        if message_id is not None:
            order.tg_message_id = message_id
            await session.commit()

    return OrderCreated(order_id=order.id, status=order.status, total=order.total)


async def _order_actors(
    session: AsyncSession, order: Order
) -> dict[OrderStatus, str]:
    """Имена тех, кто взял заказ в работу и кто его отнёс."""
    rows = (
        await session.execute(
            select(OrderStatusLog.to_status, OrderStatusLog.actor_telegram_id)
            .where(
                OrderStatusLog.order_id == order.id,
                OrderStatusLog.to_status.in_(
                    [OrderStatus.accepted, OrderStatus.served]
                ),
                OrderStatusLog.actor_telegram_id.is_not(None),
            )
            .order_by(OrderStatusLog.id)
        )
    ).all()

    roles = {OrderStatus.accepted: StaffRole.cook, OrderStatus.served: StaffRole.waiter}
    result: dict[OrderStatus, str] = {}
    for to_status, telegram_id in rows:
        name = await staff_name(
            session, telegram_id, order.branch_id, roles.get(to_status)
        )
        if name:
            result[to_status] = name
    return result


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, session: AsyncSession = Depends(get_session)):
    """Статус заказа — для поллинга с фронта («Готовим» / «Готово»)."""
    order = await session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    actors = await _order_actors(session, order)
    zone_name = await session.scalar(
        select(Zone.name).where(Zone.id == order.zone_id)
    )
    return OrderOut(
        id=order.id,
        number=order_label(order, zone_name),
        status=order.status,
        created_at=order.created_at,
        total=order.total,
        comment=order.comment,
        cooked_by=actors.get(OrderStatus.accepted),
        served_by=actors.get(OrderStatus.served),
        items=[
            OrderItemOut(dish_name=i.dish_name_snapshot, qty=i.qty, price=i.price_snapshot)
            for i in order.items
        ],
    )
