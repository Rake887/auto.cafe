"""Отправка сообщений о заказе в общий чат заведения.

Все функции безопасны при выключенном боте (BOT_TOKEN пуст) и не роняют
запрос при недоступности Telegram — заказ важнее уведомления.
"""

import html
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.instance import bot
from app.core.config import get_settings
from app.models import Order, OrderStatus, Point
from app.services.orders import CANCEL_REASONS, VisitOrder, order_label

logger = logging.getLogger(__name__)


def _order_summary(order: Order, point: Point, zone_name: str | None) -> str:
    lines = [
        f"<b>Заказ {order_label(order, zone_name)}</b> — {html.escape(point.label)}",
        "",
    ]
    for item in order.items:
        name = html.escape(item.dish_name_snapshot)
        if item.unavailable_at is not None:
            # Вычеркнутое, а не удалённое: повару важно видеть, что позиция
            # была, — иначе он решит, что состав заказа ему померещился
            lines.append(f"• <s>{name} × {item.qty}</s> — 🚫 закончилось")
            continue
        lines.append(
            f"• {name} × {item.qty} — {item.price_snapshot * item.qty} ₸"
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


def stop_categories_kb(categories: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Категории меню кнопками. По одной в строке: жмут пальцем на бегу."""
    return _kb([(name, f"stopcat:{cid}") for cid, name in categories])


def stop_dishes_kb(dishes: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    """Блюда категории с отметкой наличия. Тап переключает.

    Значок показывает текущее состояние, а не действие: «✅ Плов» значит
    «плов есть», и после нажатия он станет «🚫 Плов». Обратное прочтение
    («нажми, чтобы включить») путало бы на скорости.
    """
    rows = [
        (f"{'✅' if active else '🚫'} {name}", f"stoptog:{did}")
        for did, name, active in dishes
    ]
    rows.append(("← К категориям", "stopback"))
    return _kb(rows)


# Этап заказа одним словом — для списка заказов стола, где на строку
# приходится по три поля и разворачиваться некуда
STATUS_WORDS = {
    OrderStatus.new: "принят",
    OrderStatus.accepted: "готовится",
    OrderStatus.ready: "готов",
    OrderStatus.served: "на столе",
    OrderStatus.cancelled: "отменён",
}


def _visit_block(visit: list[VisitOrder], current_order_id: int) -> str:
    """Состав визита под заказом. Пусто, если заказ за визит первый.

    Официант обслуживает стол, а не заказ: ему нужно на одном экране видеть,
    что по этому столу уже готовится и на сколько всего набрали. Иначе он
    листает чат вверх в час пик — или не листает и несёт первый заказ, не зная
    про второй.
    """
    if len(visit) < 2:
        return ""

    lines = ["", f"➕ <b>ДОЗАКАЗ</b> — {len(visit)}-й заказ за визит."]
    if any(o.in_progress and o.id != current_order_id for o in visit):
        lines.append(
            "<i>Предыдущий заказ этого стола ещё не отдан — возможно, "
            "стоит нести вместе.</i>"
        )
    lines += ["", "🧾 <b>По столу:</b>"]
    for o in visit:
        mark = " ← этот" if o.id == current_order_id else ""
        lines.append(
            f"• {html.escape(o.label)} — {STATUS_WORDS[o.status]}, {o.total} ₸{mark}"
        )
    lines.append(f"<b>Итого по столу: {sum(o.total for o in visit)} ₸</b>")
    return "\n".join(lines)


async def notify_new_order(
    order: Order,
    point: Point,
    zone_name: str | None = None,
    visit: list[VisitOrder] | None = None,
    needs_presence: bool = False,
) -> int | None:
    """Сообщение о новом заказе с кнопкой [Принял]. Возвращает message_id.

    visit — все живые заказы стола, включая этот. Счёт официант приносит один
    на визит, и складывать его в уме он не должен.

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
    text += _visit_block(visit or [], order.id)

    if needs_presence:
        text += (
            "\n\n🪑 <b>Проверьте стол.</b> Система не смогла подтвердить, что "
            "гость в зале. Готовить начинаем после подтверждения."
        )

    try:
        msg = await bot.send_message(
            settings.group_chat_id,
            text,
            reply_markup=_kb(order_buttons(order, needs_presence)),
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
    visit: list[VisitOrder] | None = None,
) -> None:
    """За стол поручились — вернуть сообщению обычную кнопку [Принял]."""
    settings = get_settings()
    if bot is None:
        return

    text = _order_summary(order, point, zone_name)
    text += _visit_block(visit or [], order.id)
    text += f"\n\n🪑 <i>Стол подтвердил: {html.escape(actor_name)}</i>"

    try:
        await bot.edit_message_text(
            text,
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(order_buttons(order)),
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
            reply_markup=_kb(order_buttons(order)),
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
            reply_markup=_kb(order_buttons(order)),
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


def order_buttons(order: Order, needs_presence: bool = False) -> list[tuple[str, str]]:
    """Кнопки, соответствующие текущему состоянию заказа.

    Нужны в двух местах: при первой отрисовке и когда официант передумал
    отменять и надо вернуть всё как было.
    """
    if order.status is OrderStatus.new:
        first = (
            ("🪑 Гость за столом", f"presence:{order.id}")
            if needs_presence
            else ("✅ Принял", f"accept:{order.id}")
        )
    elif order.status is OrderStatus.accepted:
        first = ("🍽 Готово", f"ready:{order.id}")
    elif order.status is OrderStatus.ready:
        first = ("🙋 Обслуживаю", f"serve:{order.id}")
    else:
        return []

    buttons = [first, ("🚫 Отменить", f"cancel:{order.id}")]
    # Пока есть что вычёркивать. Когда вычеркнули всё, заказ уже отменён и
    # до этой ветки не доходит, но условие оставляем явным
    if any(i.unavailable_at is None for i in order.items):
        buttons.append(("🍽️❌ Блюдо кончилось", f"oos:{order.id}"))
    return buttons


async def ask_cancel_reason(message_id: int, order: Order) -> None:
    """Второй тап отмены: спрашиваем причину.

    Меняем только кнопки, текст заказа остаётся на месте — официанту всё ещё
    надо видеть, что именно он собирается отменить. Подтверждение здесь не
    формальность: кнопка стоит рядом с «Готово», и промах в час пик убил бы
    заказ молча.
    """
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(
                [
                    ("🪑 За столом никого", f"cancelx:{order.id}:empty_table"),
                    ("🙅 Гость передумал", f"cancelx:{order.id}:guest_left"),
                    ("← Не отменять", f"cancelno:{order.id}"),
                ]
            ),
        )
    except Exception:
        logger.exception("Failed to ask cancel reason for order %s", order.id)


async def ask_serve_anyway(
    message_id: int, order: Order, pending: list[VisitOrder]
) -> None:
    """По столу готовится ещё заказ — переспросить, нести ли этот сейчас.

    Не запрет, а вопрос: решает официант. Часть гостей ждёт всё разом, часть
    просит нести по мере готовности, и угадывать за них система не должна —
    её дело напомнить, что стол не закрыт.
    """
    settings = get_settings()
    if bot is None:
        return
    # Чего именно ждём — в кнопке отказа: текст сообщения не трогаем, официант
    # должен видеть состав заказа, который держит в руках
    waiting = ", ".join(o.label for o in pending)[:40]
    try:
        await bot.edit_message_reply_markup(
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(
                [
                    ("🙋 Всё равно нести", f"servex:{order.id}"),
                    (f"⏳ Дождусь: {waiting}", f"back:{order.id}"),
                ]
            ),
        )
    except Exception:
        logger.exception("Failed to ask serve confirmation for order %s", order.id)


async def ask_unavailable_item(message_id: int, order: Order) -> None:
    """Официант жмёт «Блюдо кончилось»: чего именно не оказалось.

    Как и у отмены, меняем только кнопки: состав заказа должен остаться перед
    глазами, иначе выбирать придётся по памяти. Уже вычеркнутые позиции в
    список не попадают — второй раз их отмечать нечем.
    """
    settings = get_settings()
    if bot is None:
        return
    # Название режем: в кнопку на телефоне длинное всё равно не помещается,
    # а перенос на вторую строку ломает ряд кнопок
    rows = [
        (
            f"🚫 {item.dish_name_snapshot[:40]} × {item.qty}",
            f"oosx:{item.id}",
        )
        for item in order.items
        if item.unavailable_at is None
    ]
    try:
        await bot.edit_message_reply_markup(
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(rows + [("← Всё на месте", f"back:{order.id}")]),
        )
    except Exception:
        logger.exception("Failed to ask unavailable item for order %s", order.id)


async def edit_order_item_unavailable(
    message_id: int,
    order: Order,
    point: Point,
    dish_name: str,
    actor_name: str,
    zone_name: str | None = None,
    needs_presence: bool = False,
) -> None:
    """Позицию вычеркнули: пересобрать сообщение с новым составом и итогом.

    Итог меняется сразу — официант понесёт счёт по нему, и пересчитывать в
    уме то, что кухня не отдала, он не должен.
    """
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_text(
            _order_summary(order, point, zone_name)
            + f"\n\n🚫 <b>{html.escape(dish_name)}</b> — закончилось "
            f"({html.escape(actor_name)}).\nГость уже видит это у себя "
            "на странице заказа.",
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(order_buttons(order, needs_presence)),
        )
    except Exception:
        logger.exception("Failed to edit unavailable item for order %s", order.id)


async def restore_order_buttons(
    message_id: int, order: Order, needs_presence: bool = False
) -> None:
    """Официант передумал отменять — вернуть кнопки по текущему статусу."""
    settings = get_settings()
    if bot is None:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=settings.group_chat_id,
            message_id=message_id,
            reply_markup=_kb(order_buttons(order, needs_presence)),
        )
    except Exception:
        logger.exception("Failed to restore buttons for order %s", order.id)


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
    reason = CANCEL_REASONS.get(order.cancel_reason or "")
    try:
        await bot.edit_message_text(
            f"🚫 <b>Заказ {order_label(order, zone_name)}</b> "
            f"({html.escape(point.label)}) отменён"
            + (f": {reason}" if reason else "")
            + f".\n👤 {html.escape(actor_name)}",
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
