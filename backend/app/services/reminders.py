"""Напоминания о том, до чего в чате не дошли руки.

Худший сценарий для заведения — гость сидит и ждёт, а заказ или вызов висит в
чате непринятым, потому что на телефон никто не смотрит. Проверка идёт фоном и
дёргает чат повторно, ровно один раз на заказ и на вызов.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.models import Order, OrderStatus, Point, ServiceCall, Zone
from app.services import telegram_notify

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 60
# Вызовы старше этого возраста уже неактуальны: гость либо дождался, либо ушёл
CALL_ESCALATION_MAX_MINUTES = 30


async def send_due_reminders() -> int:
    """Отправить напоминания по «зависшим» заказам. Возвращает их число."""
    settings = get_settings()
    if not settings.order_reminder_minutes:
        return 0

    now = datetime.now(UTC)
    deadline = now - timedelta(minutes=settings.order_reminder_minutes)
    too_old = now - timedelta(minutes=settings.order_reminder_max_minutes)
    async with async_session_factory() as session:
        stale = (
            await session.scalars(
                select(Order)
                .where(
                    Order.status == OrderStatus.new,
                    Order.created_at <= deadline,
                    # про вчерашние заказы напоминать бессмысленно
                    Order.created_at >= too_old,
                    Order.reminded_at.is_(None),
                )
                .order_by(Order.id)
                .limit(20)
            )
        ).all()
        if not stale:
            return 0

        for order in stale:
            point = await session.get_one(Point, order.point_id)
            zone_name = await session.scalar(
                select(Zone.name).where(Zone.id == point.zone_id)
            )
            waiting = int((datetime.now(UTC) - order.created_at).total_seconds() // 60)
            await telegram_notify.notify_order_stale(order, point, waiting, zone_name)
            # метку ставим независимо от успеха отправки: если Telegram лежит,
            # долбить его каждую минуту по одному и тому же заказу незачем
            order.reminded_at = datetime.now(UTC)
        await session.commit()

    logger.info("Напоминание отправлено по %s зависшим заказам", len(stale))
    return len(stale)


async def escalate_stale_calls() -> int:
    """Повторно дёрнуть чат по вызовам, которые никто не принял за SLA.

    Гость, который зовёт официанта и не дожидается, уходит с испорченным
    впечатлением молча — поэтому просроченный вызов должен шуметь второй раз.
    """
    settings = get_settings()
    if not settings.service_call_sla_seconds:
        return 0

    now = datetime.now(UTC)
    deadline = now - timedelta(seconds=settings.service_call_sla_seconds)
    too_old = now - timedelta(minutes=CALL_ESCALATION_MAX_MINUTES)
    async with async_session_factory() as session:
        stale = (
            await session.scalars(
                select(ServiceCall)
                .where(
                    ServiceCall.resolved_at.is_(None),
                    ServiceCall.created_at <= deadline,
                    ServiceCall.created_at >= too_old,
                    ServiceCall.escalated_at.is_(None),
                )
                .order_by(ServiceCall.id)
                .limit(20)
            )
        ).all()
        if not stale:
            return 0

        for call in stale:
            point = await session.get_one(Point, call.point_id)
            waiting = int((datetime.now(UTC) - call.created_at).total_seconds())
            await telegram_notify.notify_call_stale(call.id, point, waiting)
            # метку ставим независимо от успеха отправки — как и у заказов,
            # долбить лежащий Telegram каждую минуту незачем
            call.escalated_at = datetime.now(UTC)
        await session.commit()

    logger.info("Эскалация отправлена по %s просроченным вызовам", len(stale))
    return len(stale)


async def reminder_watcher() -> None:
    """Фоновый цикл: раз в минуту проверяет непринятые заказы и вызовы."""
    settings = get_settings()
    if not settings.order_reminder_minutes and not settings.service_call_sla_seconds:
        logger.info("Напоминания и эскалация выключены настройками")
        return
    while True:
        try:
            await send_due_reminders()
            await escalate_stale_calls()
        except Exception:
            logger.exception("Сбой при рассылке напоминаний")
        await asyncio.sleep(CHECK_INTERVAL_SEC)
