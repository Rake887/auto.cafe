"""Хендлеры бота: регистрация персонала по инвайту и кнопки потока заказа."""

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.models import (
    Branch,
    Category,
    Dish,
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


async def _active_staff(telegram_id: int) -> Staff | None:
    """Зарегистрированный и не уволенный сотрудник, иначе None."""
    async with async_session_factory() as session:
        return await session.scalar(
            select(Staff).where(
                Staff.telegram_chat_id == telegram_id,
                Staff.is_active.is_(True),
            )
        )


async def _branch_id() -> int | None:
    settings = get_settings()
    async with async_session_factory() as session:
        return await session.scalar(
            select(Branch.id)
            .where(Branch.organization_id == settings.demo_organization_id)
            .order_by(Branch.id)
            .limit(1)
        )


async def _categories(branch_id: int) -> list[tuple[int, str]]:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(Category.id, Category.name)
                .where(
                    Category.branch_id == branch_id,
                    Category.is_archived.is_(False),
                )
                .order_by(Category.sort_order, Category.id)
            )
        ).all()
    return [(cid, name) for cid, name in rows]


async def _dishes(category_id: int) -> tuple[str, list[tuple[int, str, bool]]]:
    async with async_session_factory() as session:
        name = await session.scalar(
            select(Category.name).where(Category.id == category_id)
        )
        rows = (
            await session.execute(
                select(Dish.id, Dish.name, Dish.is_active)
                .where(
                    Dish.category_id == category_id,
                    Dish.is_archived.is_(False),
                )
                .order_by(Dish.sort_order, Dish.id)
            )
        ).all()
    return name or "", [(did, dname, active) for did, dname, active in rows]


STOP_HINT = (
    "Что сейчас есть, а чего нет. Тап переключает — гости увидят "
    "изменение в течение двадцати секунд."
)


def _stop_text(category_name: str) -> str:
    return f"<b>{category_name}</b>\n{STOP_HINT}"


@router.message(Command("stop", "стоп"))
async def stop_list(message: Message) -> None:
    """Стоп-лист из чата: блюдо кончилось на кухне, а не в кабинете владельца.

    Право есть только у зарегистрированного персонала: спрятать блюдо — это
    потерянная выручка до тех пор, пока кто-нибудь не заметит, а в общем чате
    заведения могут сидеть посторонние.
    """
    if message.from_user is None:
        return
    if await _active_staff(message.from_user.id) is None:
        await message.answer(
            "Стоп-лист ведут сотрудники заведения. Попросите владельца "
            "прислать вам личную ссылку-приглашение."
        )
        return

    branch_id = await _branch_id()
    if branch_id is None:
        await message.answer("Заведение не найдено.")
        return
    categories = await _categories(branch_id)
    if not categories:
        await message.answer("В меню пока нет категорий.")
        return
    await message.answer(
        STOP_HINT, reply_markup=telegram_notify.stop_categories_kb(categories)
    )


@router.callback_query(F.data.startswith("stopcat:"))
async def stop_category(callback: CallbackQuery) -> None:
    """Открыть блюда выбранной категории."""
    category_id = _order_id_from(callback.data)
    if category_id is None or callback.from_user is None:
        await callback.answer("Некорректные данные кнопки")
        return
    if await _active_staff(callback.from_user.id) is None:
        await callback.answer("Только для сотрудников заведения", show_alert=True)
        return

    name, dishes = await _dishes(category_id)
    if callback.message is not None:
        await callback.message.edit_text(
            _stop_text(name),
            reply_markup=telegram_notify.stop_dishes_kb(dishes),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("stoptog:"))
async def stop_toggle(callback: CallbackQuery) -> None:
    """Переключить наличие блюда."""
    dish_id = _order_id_from(callback.data)
    if dish_id is None or callback.from_user is None:
        await callback.answer("Некорректные данные кнопки")
        return
    if await _active_staff(callback.from_user.id) is None:
        await callback.answer("Только для сотрудников заведения", show_alert=True)
        return

    async with async_session_factory() as session:
        dish = await session.get(Dish, dish_id)
        if dish is None or dish.is_archived:
            await callback.answer("Блюдо не найдено", show_alert=True)
            return
        dish.is_active = not dish.is_active
        category_id, dish_name, now_active = (
            dish.category_id,
            dish.name,
            dish.is_active,
        )
        await session.commit()

    name, dishes = await _dishes(category_id)
    if callback.message is not None:
        await callback.message.edit_text(
            _stop_text(name),
            reply_markup=telegram_notify.stop_dishes_kb(dishes),
        )
    await callback.answer(
        f"{dish_name}: {'в продаже' if now_active else 'убрано из меню'}"
    )


@router.callback_query(F.data == "stopback")
async def stop_back(callback: CallbackQuery) -> None:
    """Вернуться к списку категорий."""
    if callback.from_user is None or await _active_staff(callback.from_user.id) is None:
        await callback.answer("Только для сотрудников заведения", show_alert=True)
        return
    branch_id = await _branch_id()
    if branch_id is None or callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text(
        STOP_HINT,
        reply_markup=telegram_notify.stop_categories_kb(await _categories(branch_id)),
    )
    await callback.answer()


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
        "Доступные команды: /start, /chatid, /stop — что закончилось на кухне."
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


async def _order_and_presence(order_id: int) -> tuple[Order | None, bool]:
    """Заказ и признак «за стол ещё не поручились» — для отрисовки кнопок."""
    async with async_session_factory() as session:
        order = await session.get(Order, order_id)
        if order is None:
            return None, False
        needs = False
        if order.session_id is not None:
            visit = await session.get(TableSession, order.session_id)
            needs = visit is not None and visit.confirmed_at is None
        return order, needs


@router.callback_query(F.data.startswith("cancel:"))
async def on_cancel_ask(callback: CallbackQuery) -> None:
    """Первый тап отмены: показать причины, ничего не меняя."""
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return
    order, _ = await _order_and_presence(order_id)
    if order is None or order.status in (OrderStatus.served, OrderStatus.cancelled):
        await callback.answer("Этот заказ отменить уже нельзя", show_alert=True)
        return
    if callback.message is not None:
        await telegram_notify.ask_cancel_reason(callback.message.message_id, order)
    await callback.answer()


@router.callback_query(F.data.startswith("cancelno:"))
async def on_cancel_abort(callback: CallbackQuery) -> None:
    """Передумали отменять — вернуть прежние кнопки."""
    order_id = _order_id_from(callback.data)
    if order_id is None:
        await callback.answer("Некорректные данные кнопки")
        return
    order, needs_presence = await _order_and_presence(order_id)
    if order is not None and callback.message is not None:
        await telegram_notify.restore_order_buttons(
            callback.message.message_id, order, needs_presence
        )
    await callback.answer("Отмена отменена")


@router.callback_query(F.data.startswith("cancelx:"))
async def on_cancel_confirm(callback: CallbackQuery) -> None:
    """Второй тап: отменяем заказ с указанной причиной."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or not parts[1].isdigit():
        await callback.answer("Некорректные данные кнопки")
        return
    order_id, reason = int(parts[1]), parts[2]

    async with async_session_factory() as session:
        order = await advance_order_status(
            session,
            order_id,
            OrderStatus.cancelled,
            callback.from_user.id,
            cancel_reason=reason,
        )
    if order is None:
        await callback.answer("Заказ уже обслужен или отменён", show_alert=True)
        return

    actor = await _actor_name(callback.from_user.id, callback.from_user.full_name)
    point, zone_name = await _load_order_point(order)
    if callback.message is not None:
        await telegram_notify.edit_order_cancelled(
            callback.message.message_id, order, point, actor, zone_name
        )
    await callback.answer("Заказ отменён")


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
