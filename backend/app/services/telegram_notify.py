"""Отправка сообщений о заказе в общий чат заведения.

Все функции безопасны при выключенном боте (BOT_TOKEN пуст) и не роняют
запрос при недоступности Telegram — заказ важнее уведомления.
"""

import html
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.instance import bot
from app.core.config import get_settings
from app.models import Order, Point
from app.services.orders import order_label

logger = logging.getLogger(__name__)


def _order_summary(order: Order, point: Point, zone_name: str | None) -> str:
    lines = [
        f"<b>Заказ {order_label(order, zone_name)}</b> — {html.escape(point.label)}",
        "",
    ]
    for item in order.items:
        lines.append(
            f"• {html.escape(item.dish_name_snapshot)} × {item.qty} — "
            f"{item.price_snapshot * item.qty} ₸"
        )
    if order.comment:
        lines.append("")
        lines.append(f"💬 <i>{html.escape(order.comment)}</i>")
    lines.append("")
    lines.append(f"<b>Итого: {order.total} ₸</b>")
    return "\n".join(lines)


def _kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d)] for t, d in buttons]
    )


async def notify_new_order(
    order: Order,
    point: Point,
    zone_name: str | None = None,
    visit_orders: int = 1,
    visit_total: int = 0,
    needs_presence: bool = False,
) -> int | None:
    """Сообщение о новом заказе с кнопкой [Принял]. Возвращает message_id.

    visit_* — сколько заказов и на какую сумму уже набрал стол. Счёт официант
    приносит один на визит, и складывать в уме он не должен.

    needs_presence — за стол ещё никто не поручился. Тогда вместо «Принял»
    показываем «Гость за столом»: если стол пуст, никто не нажмёт, кухня не
    начнёт готовить, и заведение ничего не потеряет.
    """
    settings = get_settings()
    if bot is None:
        logger.info("BOT_TOKEN не задан — уведомление о заказе %s пропущено", order.id)
        return None
    if not settings.group_chat_id:
        logger.warning(
            "GROUP_CHAT_ID не задан — заказ %s создан, но в чат не отправлен. "
            "Добавьте бота в группу заведения, он подскажет chat_id",
            order.id,
        )
        return None
    text = _order_summary(order, point, zone_name)
    if order.is_remote:
        # не блокируем: GPS в помещении врёт, а гость мог сидеть у окна.
        # Решает официант — он видит стол своими глазами.
        text += "\n\n⚠️ <i>Телефон гостя далеко от заведения — проверьте стол</i>"
    if visit_orders > 1:
        text += (
            f"\n\n🧾 <i>Заказ {visit_orders}-й за визит, "
            f"итого по столу {visit_total} ₸</i>"
        )

    if needs_presence:
        text += (
            "\n\n🪑 <b>Проверьте стол.</b> Система не смогла подтвердить, что "
            "гость в зале. Готовить начинаем после подтверждения."
        )
        buttons = [("🪑 Гость за столом", f"presence:{order.id}")]
    else:
        buttons = [("✅ Принял", f"accept:{order.id}")]

    try:
        msg = await bot.send_message(
            settings.group_chat_id, text, reply_markup=_kb(buttons)
        )
        return msg.message_id
    except Exception:
        logger.exception("Failed to send new-order notification for order %s", order.id)
        return None


async def edit_order_presence_confirmed(
    message_id: int,
    order: Order,
    point: Point,
    zone_name: str | None,
    actor_name: str,
    visit_orders: int = 1,
    visit_total: int = 0,
) -> None:
    """За стол поручились — вернуть сообщению обычную кнопку [Принял]."""
    settings = get_settings()
    if bot is None:
        return

    text = _order_summary(order, point, zone_name)
    if visit_orders > 1:
        text += (
            f"\n\n🧾 <i>Заказ {visit_orders}-й за визит, "
            f"итого по столу {visit_total} ₸</i>"
        )
    text += f"\n\n🪑 <i>Стол подтвердил: {html.escape(actor_name)}</i>"

    try:
        await bot.edit_message_text(
            text,
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb([("✅ Принял", f"accept:{order.id}")]),
        )
    except Exception:
        logger.exception("Failed to edit presence message for order %s", order.id)


async def edit_order_accepted(
    message_id: int,
    order: Order,
    point: Point,
    actor_name: str,
    zone_name: str | None = None,
) -> None:
    """Заказ принят поваром: убрать [Принял], показать кто принял, дать [Готово]."""
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            _order_summary(order, point, zone_name)
            + f"\n\n👨‍🍳 Принял: {html.escape(actor_name)}",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb([("🍽 Готово", f"ready:{order.id}")]),
        )
    except Exception:
        logger.exception("Failed to edit accepted message for order %s", order.id)


async def edit_order_done_cooking(
    message_id: int,
    order: Order,
    point: Point,
    actor_name: str,
    zone_name: str | None = None,
) -> None:
    """Финализировать исходное сообщение заказа (кнопки убрать)."""
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            _order_summary(order, point, zone_name)
            + f"\n\n✅ Приготовлен ({html.escape(actor_name)})",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except Exception:
        logger.exception("Failed to edit ready message for order %s", order.id)


async def notify_order_ready(
    order: Order, point: Point, zone_name: str | None = None
) -> int | None:
    """НОВОЕ сообщение для официантов: заказ готов, кнопка [Обслуживаю]."""
    settings = get_settings()
    if bot is None or not settings.group_chat_id:
        return None
    try:
        msg = await bot.send_message(
            settings.group_chat_id,
            f"🔔 <b>Заказ {order_label(order, zone_name)} готов!</b>\n"
            f"{html.escape(point.label)} — отнести гостю.",
            reply_markup=_kb([("🙋 Обслуживаю", f"serve:{order.id}")]),
        )
        return msg.message_id
    except Exception:
        logger.exception("Failed to send ready notification for order %s", order.id)
        return None


async def edit_order_served(
    message_id: int,
    order: Order,
    point: Point,
    actor_name: str,
    zone_name: str | None = None,
) -> None:
    """Официант забрал заказ: отредактировать «готов»-сообщение."""
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            f"✅ <b>Заказ {order_label(order, zone_name)}</b> ({html.escape(point.label)}) обслужен.\n"
            f"🙋 {html.escape(actor_name)}",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except Exception:
        logger.exception("Failed to edit served message for order %s", order.id)


async def edit_order_cancelled(
    message_id: int,
    order: Order,
    point: Point,
    actor_name: str,
    zone_name: str | None = None,
) -> None:
    """Владелец отменил заказ из кабинета: погасить кнопки в чате.

    Без этого на отменённом заказе остаются живые [Принял] / [Готово], и кухня
    начнёт готовить то, что уже отменили.
    """
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            f"🚫 <b>Заказ {order_label(order, zone_name)}</b> ({html.escape(point.label)}) отменён.\n"
            f"👤 {html.escape(actor_name)}",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except Exception:
        logger.exception("Failed to edit cancelled message for order %s", order.id)


async def notify_order_stale(
    order: Order, point: Point, minutes: int, zone_name: str | None = None
) -> int | None:
    """Заказ висит непринятым — напомнить кухне отдельным сообщением.

    Кнопка та же, что у нового заказа: повар может принять прямо отсюда.
    """
    settings = get_settings()
    if bot is None or not settings.group_chat_id:
        return None
    try:
        msg = await bot.send_message(
            settings.group_chat_id,
            f"⏰ <b>Заказ {order_label(order, zone_name)}</b> ждёт {minutes} мин — его никто не взял.\n"
            f"{html.escape(point.label)}, на {order.total} ₸.",
            reply_markup=_kb([("✅ Принял", f"accept:{order.id}")]),
        )
        return msg.message_id
    except Exception:
        logger.exception("Failed to send stale reminder for order %s", order.id)
        return None


async def notify_service_call(
    call_id: int, point: Point, comment: str | None = None
) -> int | None:
    """Гость позвал официанта: сообщение в чат с кнопкой [Иду]."""
    settings = get_settings()
    if bot is None or not settings.group_chat_id:
        logger.info("Bot disabled, skip service call %s", call_id)
        return None
    try:
        msg = await bot.send_message(
            settings.group_chat_id,
            f"🔔 <b>{html.escape(point.label)}</b> зовёт официанта."
            + (f"\n💬 <i>{html.escape(comment)}</i>" if comment else ""),
            reply_markup=_kb([("🙋 Иду", f"call:{call_id}")]),
        )
        return msg.message_id
    except Exception:
        logger.exception("Failed to send service call %s", call_id)
        return None


async def notify_bad_review(
    order: Order,
    point: Point,
    zone_name: str | None,
    rating: int,
    comment: str | None,
    cooked_by: str | None,
    served_by: str | None,
) -> int | None:
    """Гость поставил низкую оценку — сообщить в чат, пока он ещё за столом.

    Смысл именно в скорости: извиниться и исправить можно только пока человек
    не ушёл. Через час это уже публичный отзыв, на который нечего ответить.
    """
    settings = get_settings()
    if bot is None or not settings.group_chat_id:
        return None

    served = ", ".join(filter(None, [cooked_by, served_by]))
    lines = [
        f"⚠️ <b>Оценка {rating}/5</b> — {html.escape(point.label)}",
        f"Заказ {order_label(order, zone_name)} на {order.total} ₸",
    ]
    if comment:
        lines.append(f"💬 <i>{html.escape(comment)}</i>")
    if served:
        lines.append(f"Смена: {html.escape(served)}")
    lines.append("")
    lines.append("Гость ещё может быть в зале — подойдите к столу.")

    try:
        msg = await bot.send_message(settings.group_chat_id, "\n".join(lines))
        return msg.message_id
    except Exception:
        logger.exception("Failed to send bad review for order %s", order.id)
        return None


async def notify_call_stale(call_id: int, point: Point, seconds: int) -> int | None:
    """Вызов висит непринятым дольше SLA — дёрнуть чат повторно.

    Кнопка та же, что у исходного вызова: подойти можно прямо отсюда.
    """
    settings = get_settings()
    if bot is None or not settings.group_chat_id:
        return None
    try:
        msg = await bot.send_message(
            settings.group_chat_id,
            f"🚨 <b>{html.escape(point.label)}</b> зовёт официанта уже "
            f"{seconds} секунд — никто не подошёл.",
            reply_markup=_kb([("🙋 Иду", f"call:{call_id}")]),
        )
        return msg.message_id
    except Exception:
        logger.exception("Failed to escalate service call %s", call_id)
        return None


async def edit_service_call_taken(
    message_id: int, point: Point, actor_name: str
) -> None:
    """Официант принял вызов — убрать кнопку, показать кто идёт."""
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            f"✅ <b>{html.escape(point.label)}</b> — идёт {html.escape(actor_name)}.",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except Exception:
        logger.exception("Failed to edit service call message %s", message_id)
