"""Что происходит в зале прямо сейчас, и история вызовов официанта.

Владелец открывает кабинет посреди смены не ради выручки за неделю, а чтобы
увидеть, не завис ли заказ и не машет ли кто-то рукой у столика. Поэтому эти
цифры считаются отдельной лёгкой ручкой, которую экран дёргает каждые 15 секунд.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_branch, require_admin
from app.core.db import get_session
from app.models import (
    Branch,
    Order,
    OrderItem,
    OrderStatus,
    Point,
    Review,
    ServiceCall,
    TableSession,
    Zone,
)
from app.schemas.admin import (
    AdminServiceCallOut,
    OpenCallOut,
    OpenVisitOut,
    PulseOut,
)
from app.services.staff_lookup import staff_by_telegram
from app.services.stats import PERIODS, period_start

router = APIRouter(prefix="/admin", tags=["admin"])


def _waited(since: datetime, until: datetime | None = None) -> int:
    """Сколько секунд ждали. Отрицательного не бывает — часы могут расходиться."""
    end = until or datetime.now(UTC)
    return max(0, int((end - since).total_seconds()))


@router.get("/pulse", response_model=PulseOut)
async def pulse(
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Сводка «сейчас в зале» — первый экран кабинета."""
    new, cooking, ready, oldest_new = (
        await session.execute(
            select(
                func.count().filter(Order.status == OrderStatus.new),
                func.count().filter(Order.status == OrderStatus.accepted),
                func.count().filter(Order.status == OrderStatus.ready),
                func.min(Order.created_at).filter(Order.status == OrderStatus.new),
            ).where(Order.branch_id == branch.id)
        )
    ).one()

    open_calls = (
        await session.execute(
            select(ServiceCall, Point.label, Zone.name)
            .join(Point, Point.id == ServiceCall.point_id)
            .join(Zone, Zone.id == Point.zone_id)
            .where(
                ServiceCall.branch_id == branch.id,
                ServiceCall.resolved_at.is_(None),
            )
            .order_by(ServiceCall.created_at)
        )
    ).all()

    unresolved_reviews = await session.scalar(
        select(func.count())
        .select_from(Review)
        .where(
            Review.branch_id == branch.id,
            Review.resolved_at.is_(None),
            Review.rating <= 3,
        )
    )

    # Открытые визиты с итогом: официанту нужен один счёт на стол, а не три
    # отдельных заказа с трёх телефонов
    line_total = OrderItem.price_snapshot * OrderItem.qty
    visits = (
        await session.execute(
            select(
                TableSession.id,
                TableSession.opened_at,
                Point.label,
                Zone.name,
                func.count(func.distinct(Order.id)),
                func.coalesce(func.sum(line_total), 0),
                func.bool_or(Order.is_remote),
                TableSession.confirmed_at,
            )
            .select_from(TableSession)
            .join(Point, Point.id == TableSession.point_id)
            .join(Zone, Zone.id == Point.zone_id)
            .join(
                Order,
                (Order.session_id == TableSession.id)
                & (Order.status != OrderStatus.cancelled),
            )
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                TableSession.branch_id == branch.id,
                TableSession.closed_at.is_(None),
            )
            .group_by(
                TableSession.id,
                TableSession.opened_at,
                TableSession.confirmed_at,
                Point.label,
                Zone.name,
            )
            .order_by(TableSession.opened_at)
        )
    ).all()

    return PulseOut(
        orders_new=new,
        orders_cooking=cooking,
        orders_ready=ready,
        oldest_new_minutes=(
            _waited(oldest_new) // 60 if oldest_new is not None else None
        ),
        open_calls=[
            OpenCallOut(
                id=call.id,
                point_label=label,
                zone_name=zone_name,
                comment=call.comment,
                waiting_seconds=_waited(call.created_at),
                escalated=call.escalated_at is not None,
            )
            for call, label, zone_name in open_calls
        ],
        unresolved_reviews=unresolved_reviews or 0,
        open_visits=[
            OpenVisitOut(
                id=visit_id,
                point_label=label,
                zone_name=zone_name,
                orders=orders,
                total=int(total),
                opened_at=opened_at,
                has_remote=bool(has_remote),
                confirmed=confirmed_at is not None,
            )
            for (
                visit_id,
                opened_at,
                label,
                zone_name,
                orders,
                total,
                has_remote,
                confirmed_at,
            ) in visits
        ],
    )


@router.post("/visits/{visit_id}/close", status_code=204)
async def close_visit(
    visit_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Счёт закрыт: следующий заказ с этого стола откроет новый визит."""
    visit = await session.get(TableSession, visit_id)
    if visit is None or visit.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Визит не найден")
    if visit.closed_at is None:
        visit.closed_at = datetime.now(UTC)
        await session.commit()


@router.get("/calls", response_model=list[AdminServiceCallOut])
async def admin_calls(
    period: str = Query(default="day"),
    limit: int = Query(default=100, ge=1, le=500),
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """История вызовов за период: кто звал, сколько ждал и кто подошёл."""
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period: {', '.join(PERIODS)}")

    stmt = (
        select(ServiceCall, Point.label, Zone.name)
        .join(Point, Point.id == ServiceCall.point_id)
        .join(Zone, Zone.id == Point.zone_id)
        .where(ServiceCall.branch_id == branch.id)
        .order_by(ServiceCall.id.desc())
        .limit(limit)
    )
    since = period_start(period)
    if since is not None:
        stmt = stmt.where(ServiceCall.created_at >= since)

    rows = (await session.execute(stmt)).all()

    # имена принявших — одним запросом на всю выборку, а не по одному на строку
    by_chat = await staff_by_telegram(
        session,
        [c.actor_telegram_id for c, _, _ in rows if c.actor_telegram_id is not None],
        branch.id,
    )

    return [
        AdminServiceCallOut(
            id=call.id,
            created_at=call.created_at,
            point_label=label,
            zone_name=zone_name,
            comment=call.comment,
            resolved_at=call.resolved_at,
            waiting_seconds=_waited(call.created_at, call.resolved_at),
            escalated=call.escalated_at is not None,
            taken_by=(
                staff.full_name
                if (staff := by_chat.get(call.actor_telegram_id)) is not None
                else None
            ),
        )
        for call, label, zone_name in rows
    ]


@router.post("/calls/{call_id}/resolve", status_code=204)
async def resolve_call(
    call_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Закрыть вызов из кабинета: официант подошёл, а «Иду» никто не нажал."""
    call = await session.get(ServiceCall, call_id)
    if call is None or call.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Вызов не найден")
    if call.resolved_at is None:
        # actor_telegram_id не трогаем: подошёл кто-то из зала, а кто — неизвестно
        call.resolved_at = datetime.now(UTC)
        await session.commit()
