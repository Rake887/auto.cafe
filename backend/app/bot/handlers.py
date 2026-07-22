"""Хендлеры бота: регистрация персонала по инвайту и кнопки потока заказа."""

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select

from app.core.db import async_session_factory
from app.models import (
    Order,
    OrderStatus,
    Point,
    ServiceCall,
    Staff,
    TableSession,
    Zone,
)
from app.services.orders import advance_order_status, visit_totals
from app.services import telegram_notify

logger = logging.getLogger(__name__)

router = Router()

ROLE_TITLES = {"cook": "повар", "waiter": "официант"}


@router.message(CommandStart(deep_link=True))
async def start_with_invite(message: Message, command: CommandObject) -> None:
    """/start <invite_token> — активация одноразового приглашения сотрудника."""
    token = (command.args or "").strip()
    async with async_session_factory() as session:
        staff = await session.scalar(select(Staff).where(Staff.invite_token == token))
        if staff is None:
            await message.answer("Приглашение не найдено или уже использовано.")
            return
        if not staff.is_active:
            # уволенному ссылку обнуляют, но она могла остаться в чате у него
            await message.answer("Приглашение больше не действует.")
            return
        staff.telegram_chat_id = message.chat.id
        staff.invite_token = None  # токен одноразовый
        await session.commit()
    role_title = ROLE_TITLES.get(staff.role.value, staff.role.value)
    await message.answer(
        f"✅ {staff.full_name}, вы зарегистрированы как {role_title}.\n"
        "Заказы будут приходить в общий чат заведения."
    )


@router.my_chat_member()
async def on_added_to_chat(event: ChatMemberUpdated) -> None:
    """Бота добавили в чат — сразу подсказать его chat_id для GROUP_CHAT_ID."""
    if event.new_chat_member.status not in ("member", "administrator"):
        return
    logger.info(
        "Бот добавлен в чат: chat_id=%s (%s)", event.chat.id, event.chat.type
    )
    await event.bot.send_message(
        event.chat.id,
        "Готов принимать заказы.\n"
        f"chat_id этого чата: <code>{event.chat.id}</code>\n"
        "Впишите его в GROUP_CHAT_ID и перезапустите API.",
    )


@router.message(Command("chatid"))
async def chat_id(message: Message) -> None:
    """/chatid — узнать id чата, чтобы прописать его в GROUP_CHAT_ID."""
    logger.info(
        "GROUP_CHAT_ID кандидат: chat_id=%s (%s)", message.chat.id, message.chat.type
    )
    await message.answer(
        f"chat_id этого чата: <code>{message.chat.id}</code>\n"
        "Впишите его в GROUP_CHAT_ID и перезапустите API."
    )


@router.message(CommandStart())
async def start_plain(message: Message) -> None:
    await message.answer(
        "Это служебный бот QR-меню. Для регистрации сотрудника нужна "
        "персональная ссылка-приглашение от администратора.\n\n"
        "Команда /chatid покажет id этого чата."
    )


# Последний в цепочке: ловит всё, на что не нашлось хендлера выше, —
# чтобы бот не выглядел мёртвым, когда ему пишут обычный текст.
@router.message()
async def fallback(message: Message) -> None:
    if message.chat.type != "private":
        return  # в группе на болтовню персонала не отвечаем
    await message.answer(
        "Я принимаю заказы из QR-меню и показываю их кухне.\n"
        "Доступные команды: /start, /chatid."
    )


async def _actor_name(telegram_id: int, fallback: str) -> str:
    """Имя для отображения в чате: ФИО из базы (если зарегистрирован) или имя из TG."""
    async with async_session_factory() as session:
        staff = await session.scalar(
            select(Staff).where(Staff.telegram_chat_id == telegram_id)
        )
    if staff is None:
        return fallback
    role_title = ROLE_TITLES.get(staff.role.value, staff.role.value)
    return f"{staff.full_name} ({role_title})"


async def _load_order_point(order: Order) -> tuple[Point, str | None]:
    """Стол заказа и имя его зоны — зона нужна для номера «Терраса №14»."""
    async with async_session_factory() as session:
        point = await session.get_one(Point, order.point_id)
        zone_name = await session.scalar(
            select(Zone.name).where(Zone.id == point.zone_id)
        )
        return point, zone_name


def _order_id_from(data: str) -> int | None:
    try:
        return int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


@router.callback_query(F.data.startswith("presence:"))
async def on_presence(callback: CallbackQuery) -> None:
    """Официант жмёт [Гость за столом]: за визит поручились, можно готовить.

    Ручаются один раз на визит — следующие заказы того же стола приходят
    сразу с кнопкой «Принял».
    """
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return

    async with async_session_factory() as session:
        order = await session.get(Order, order_id)
        if order is None or order.session_id is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        visit = await session.get(TableSession, order.session_id)
        if visit is not None and visit.confirmed_at is None:
            visit.confirmed_at = datetime.now(UTC)
            await session.commit()
        visit_orders, visit_total = await visit_totals(session, order.session_id)

    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    point, zone_name = await _load_order_point(order)
    if callback.message is not None:
        await telegram_notify.edit_order_presence_confirmed(
            callback.message.message_id,
            order,
            point,
            zone_name,
            actor,
            visit_orders,
            visit_total,
        )
    await callback.answer("Стол подтверждён — можно готовить")


@router.callback_query(F.data.startswith("accept:"))
async def on_accept(callback: CallbackQuery) -> None:
    """Повар жмёт [Принял]: new -> accepted, редактируем сообщение заказа."""
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return
    async with async_session_factory() as session:
        order = await advance_order_status(
            session, order_id, OrderStatus.accepted, callback.from_user.id
        )
    if order is None:
        await callback.answer("Заказ уже принят или отменён", show_alert=True)
        return
    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    point, zone_name = await _load_order_point(order)
    if callback.message is not None:
        await telegram_notify.edit_order_accepted(
            callback.message.message_id, order, point, actor, zone_name
        )
    await callback.answer("Заказ принят")


@router.callback_query(F.data.startswith("ready:"))
async def on_ready(callback: CallbackQuery) -> None:
    """Повар жмёт [Готово]: accepted -> ready, новое сообщение официантам."""
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return
    async with async_session_factory() as session:
        order = await advance_order_status(
            session, order_id, OrderStatus.ready, callback.from_user.id
        )
    if order is None:
        await callback.answer("Статус уже изменён", show_alert=True)
        return
    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    point, zone_name = await _load_order_point(order)
    if callback.message is not None:
        await telegram_notify.edit_order_done_cooking(
            callback.message.message_id, order, point, actor, zone_name
        )
    await telegram_notify.notify_order_ready(order, point, zone_name)
    await callback.answer("Отмечено готовым")


@router.callback_query(F.data.startswith("serve:"))
async def on_serve(callback: CallbackQuery) -> None:
    """Официант жмёт [Обслуживаю]: ready -> served, цикл заказа завершён."""
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return
    async with async_session_factory() as session:
        order = await advance_order_status(
            session, order_id, OrderStatus.served, callback.from_user.id
        )
    if order is None:
        await callback.answer("Заказ уже обслужен", show_alert=True)
        return
    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    point, zone_name = await _load_order_point(order)
    if callback.message is not None:
        await telegram_notify.edit_order_served(
            callback.message.message_id, order, point, actor, zone_name
        )
    await callback.answer("Приятного аппетита гостю!")


@router.callback_query(F.data.startswith("call:"))
async def on_service_call(callback: CallbackQuery) -> None:
    """Официант жмёт [Иду] на вызов со стола."""
    call_id = _order_id_from(callback.data)
    if call_id is None:
        await callback.answer("Некорректные данные кнопки")
        return

    async with async_session_factory() as session:
        # блокируем строку: двойной тап не даст двух «принявших»
        call = await session.scalar(
            select(ServiceCall).where(ServiceCall.id == call_id).with_for_update()
        )
        if call is None or call.resolved_at is not None:
            await session.rollback()
            await callback.answer("Вызов уже принят", show_alert=True)
            return
        call.resolved_at = datetime.now(UTC)
        call.actor_telegram_id = callback.from_user.id
        point = await session.get_one(Point, call.point_id)
        await session.commit()

    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    if callback.message is not None:
        await telegram_notify.edit_service_call_taken(
            callback.message.message_id, point, actor
        )
    await callback.answer("Вызов принят")
