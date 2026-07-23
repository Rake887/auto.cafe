from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Branch,
    Category,
    Dish,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusLog,
    Point,
    TableSession,
    Zone,
)
from app.services.menu import is_visible_at

# Заказы с одного стола: живой стол не оформляет больше нескольких заказов
# за десять минут, а вот скрипт по украденному токену — сколько угодно
ORDER_RATE_LIMIT = 5
ORDER_RATE_WINDOW_MINUTES = 10

# Визит считается брошенным, если по столу давно ничего не заказывали:
# гости ушли, а счёт закрыть забыли
SESSION_IDLE_HOURS = 3


class PointNotFound(Exception):
    pass


class OrdersNotAccepted(Exception):
    """Заведение сейчас не принимает заказы: закрыто или включён стоп-кран."""

    def __init__(self, reason: str):
        self.reason = reason


class TooManyOrders(Exception):
    """Со стола сыплется подозрительно много заказов."""


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в метрах (гаверсинус).

    Точности формулы с лихвой хватает: мы сравниваем с радиусом в десятки
    метров, а не строим маршрут.
    """
    earth_radius_m = 6_371_000
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * earth_radius_m * asin(sqrt(a))


def closed_reason(branch: Branch, now_local: datetime | None = None) -> str | None:
    """Почему заказ сейчас не примут. None — принимают.

    Отдельная функция, потому что нужна дважды: на входе заказа и в гостевом
    меню — гость должен увидеть «закрыто» до того, как соберёт корзину.
    """
    if not branch.accepting_orders:
        return "Заведение сейчас не принимает заказы"

    if branch.opens_at is None and branch.closes_at is None:
        return None

    settings = get_settings()
    moment = now_local or datetime.now(ZoneInfo(settings.display_timezone))
    # окно через полночь считает та же функция, что и часы показа категорий
    if is_visible_at(branch.opens_at, branch.closes_at, moment.time()):
        return None

    if branch.opens_at is not None and branch.closes_at is not None:
        window = f"{branch.opens_at:%H:%M}–{branch.closes_at:%H:%M}"
        return f"Заказы принимаем с {window}"
    return "Сейчас заведение закрыто"


def order_label(order: Order, zone_name: str | None) -> str:
    """Как заказ называется для людей: «Терраса №14».

    Сквозной id к концу месяца превращается в четырёхзначное число, которое
    невозможно ни выкрикнуть, ни сверить. Номер внутри зоны за день короткий.
    Старые заказы зоны не знают — для них остаётся «#id».
    """
    if order.zone_seq is None or zone_name is None:
        return f"#{order.id}"
    return f"{zone_name} №{order.zone_seq}"


async def _next_zone_seq(session: AsyncSession, zone_id: int) -> int:
    """Следующий номер заказа в зоне, со сбросом на новый день.

    Строка зоны блокируется: два одновременных заказа не должны получить
    один номер. Поток заказов кафе таков, что это не узкое место.
    """
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.display_timezone)).date()

    zone = await session.scalar(
        select(Zone).where(Zone.id == zone_id).with_for_update()
    )
    if zone is None:
        return 0
    if zone.counter_day != today:
        zone.counter_day = today
        zone.order_counter = 0
    zone.order_counter += 1
    return zone.order_counter


class DishesNotFound(Exception):
    def __init__(self, dish_ids: list[int]):
        self.dish_ids = dish_ids


# Разрешённые переходы статусов заказа.
# Отменить можно и готовое блюдо: официант доносит его до стола и обнаруживает,
# что там никого. Еда потеряна, но выручки по этому заказу нет — значит и в
# статистику он попасть не должен.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.new: {OrderStatus.accepted, OrderStatus.cancelled},
    OrderStatus.accepted: {OrderStatus.ready, OrderStatus.cancelled},
    OrderStatus.ready: {OrderStatus.served, OrderStatus.cancelled},
}

# Почему отменили. Разница существенная: «стол пуст» на готовом заказе — это
# выброшенные продукты, а «гость передумал» до готовки не стоит ничего.
CANCEL_REASONS = {
    "empty_table": "за столом никого",
    "guest_left": "гость передумал",
}


async def get_order_by_client_request_id(
    session: AsyncSession, client_request_id: str
) -> Order | None:
    return await session.scalar(
        select(Order).where(Order.client_request_id == client_request_id)
    )


def client_ip(forwarded_for: str | None, peer: str | None) -> str | None:
    """Настоящий IP гостя из цепочки X-Forwarded-For.

    Берём ПОСЛЕДНИЙ элемент, а не первый: Caddy дописывает адрес своего
    непосредственного собеседника в конец, а всё, что левее, гость мог
    прислать сам. Первый элемент — это то, что подделывается за минуту.
    """
    if forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return peer


def is_public_ip(value: str) -> bool:
    """Годится ли адрес в качестве «IP заведения».

    Внутренние адреса (172.17.x, 10.x, 192.168.x, localhost) сюда попадают,
    когда запрос идёт не напрямую от гостя, а из docker-сети или из туннеля.
    Сохранить такой адрес — значит признать доверенными вообще все заказы,
    потому что у всех гостей он окажется одинаковым. Поэтому отвергаем.
    """
    try:
        address = ip_address(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
    )


def presence_confirmed(
    branch: Branch,
    guest_ip: str | None,
    guest_lat: float | None,
    guest_lon: float | None,
) -> bool:
    """Есть ли основание считать, что гость действительно в зале.

    Признаки автоматические и необязательные: если ни один не сработал, это
    не «злоумышленник», а просто «неизвестно» — тогда за стол ручается
    официант кнопкой в чате. Блокировать по ним нельзя, потому что оба
    подводят живых гостей: Wi-Fi есть не у всех, в геолокации отказывают.
    """
    if branch.trusted_ip and guest_ip and guest_ip == branch.trusted_ip:
        return True

    if (
        guest_lat is not None
        and guest_lon is not None
        and branch.lat is not None
        and branch.lon is not None
        and branch.geo_radius_m
    ):
        away = distance_m(
            float(branch.lat), float(branch.lon), guest_lat, guest_lon
        )
        return away <= branch.geo_radius_m

    return False


async def _current_session(
    session: AsyncSession, point: Point
) -> TableSession:
    """Открытый визит стола или новый.

    Визит открывается первым заказом, а не сканом: гость мог посмотреть меню
    и уйти, и такой «визит» только мешал бы официанту.
    """
    idle_since = datetime.now(UTC) - timedelta(hours=SESSION_IDLE_HOURS)
    visit = await session.scalar(
        select(TableSession)
        .where(
            TableSession.point_id == point.id,
            TableSession.closed_at.is_(None),
            TableSession.opened_at >= idle_since,
        )
        .order_by(TableSession.id.desc())
        .limit(1)
    )
    if visit is not None:
        return visit

    visit = TableSession(branch_id=point.branch_id, point_id=point.id)
    session.add(visit)
    await session.flush()
    return visit


async def visit_totals(
    session: AsyncSession, session_id: int | None
) -> tuple[int, int]:
    """Сколько заказов и на какую сумму набрал визит. (0, 0) — визита нет."""
    if session_id is None:
        return 0, 0
    line_total = OrderItem.price_snapshot * OrderItem.qty
    row = (
        await session.execute(
            select(
                func.count(func.distinct(Order.id)),
                func.coalesce(func.sum(line_total), 0),
            )
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.session_id == session_id,
                Order.status != OrderStatus.cancelled,
            )
        )
    ).one()
    return int(row[0]), int(row[1])


async def _too_frequent(session: AsyncSession, point_id: int) -> bool:
    since = datetime.now(UTC) - timedelta(minutes=ORDER_RATE_WINDOW_MINUTES)
    recent = await session.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.point_id == point_id, Order.created_at >= since)
    )
    return (recent or 0) >= ORDER_RATE_LIMIT


async def create_order(
    session: AsyncSession,
    point_token: str,
    client_request_id: str,
    items: list[tuple[int, int]],  # (dish_id, qty)
    comment: str | None = None,
    guest_lat: float | None = None,
    guest_lon: float | None = None,
    guest_ip: str | None = None,
) -> tuple[Order, bool]:
    """Создать заказ идемпотентно.

    Возвращает (order, created): если client_request_id уже есть в БД —
    отдаём существующий заказ и created=False, дубль не создаём.
    Цены и названия блюд берутся из БД (снапшоты), клиенту не доверяем.

    Координаты гостя необязательны: браузер мог не дать их или гость отказал.
    Они ни на что не влияют, кроме метки «заказ вне зала».
    """
    existing = await get_order_by_client_request_id(session, client_request_id)
    if existing is not None:
        return existing, False

    point = await session.scalar(
        select(Point).where(
            Point.token == point_token, Point.is_archived.is_(False)
        )
    )
    if point is None:
        raise PointNotFound()

    branch = await session.get_one(Branch, point.branch_id)
    reason = closed_reason(branch)
    if reason is not None:
        raise OrdersNotAccepted(reason)

    if await _too_frequent(session, point.id):
        raise TooManyOrders()

    dish_ids = [dish_id for dish_id, _ in items]
    dishes = {
        d.id: d
        for d in await session.scalars(
            select(Dish)
            .join(Category)
            .where(
                Dish.id.in_(dish_ids),
                Dish.is_active.is_(True),
                Category.branch_id == point.branch_id,
            )
        )
    }
    missing = [i for i in dish_ids if i not in dishes]
    if missing:
        raise DishesNotFound(missing)

    # заказ «издалека» пропускаем, но помечаем — решать официанту
    is_remote = False
    if (
        guest_lat is not None
        and guest_lon is not None
        and branch.lat is not None
        and branch.lon is not None
        and branch.geo_radius_m
    ):
        away = distance_m(
            float(branch.lat), float(branch.lon), guest_lat, guest_lon
        )
        is_remote = away > branch.geo_radius_m

    visit = await _current_session(session, point)
    # Признаки присутствия проверяем на каждом заказе, а не только на первом:
    # гость мог сначала отказать в геолокации, а со второго раза разрешить —
    # и тогда официанта дёргать уже незачем.
    if visit.confirmed_at is None and presence_confirmed(
        branch, guest_ip, guest_lat, guest_lon
    ):
        visit.confirmed_at = datetime.now(UTC)

    order = Order(
        branch_id=point.branch_id,
        point_id=point.id,
        # зону фиксируем снапшотом: стол могут перевести на террасу, и тогда
        # прошлые заказы не должны переехать вместе с ним
        zone_id=point.zone_id,
        zone_seq=await _next_zone_seq(session, point.zone_id),
        session_id=visit.id,
        is_remote=is_remote,
        status=OrderStatus.new,
        client_request_id=client_request_id,
        comment=(comment or "").strip() or None,
        items=[
            OrderItem(
                dish_id=dish_id,
                qty=qty,
                price_snapshot=dishes[dish_id].price,
                # себестоимость фиксируем вместе с ценой: завтрашняя закупка
                # не должна переписывать вчерашнюю прибыль
                cost_snapshot=dishes[dish_id].cost_price,
                dish_name_snapshot=dishes[dish_id].name,
            )
            for dish_id, qty in items
        ],
    )
    session.add(order)
    try:
        await session.flush()
        session.add(
            OrderStatusLog(order_id=order.id, from_status=None, to_status=OrderStatus.new)
        )
        await session.commit()
    except IntegrityError:
        # Конкурентный двойной тап: второй INSERT упёрся в unique(client_request_id)
        await session.rollback()
        existing = await get_order_by_client_request_id(session, client_request_id)
        if existing is None:
            raise
        return existing, False
    return order, True


async def advance_order_status(
    session: AsyncSession,
    order_id: int,
    to_status: OrderStatus,
    actor_telegram_id: int | None,
    cancel_reason: str | None = None,
) -> Order | None:
    """Перевести заказ в новый статус с проверкой допустимости перехода.

    Блокирует строку заказа (FOR UPDATE) — двойной тап по кнопке в Telegram
    не даст двойного перехода. None — переход невозможен или заказ не найден.
    """
    order = await session.scalar(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    if order is None or to_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        await session.rollback()
        return None

    from_status = order.status
    order.status = to_status
    if to_status is OrderStatus.cancelled and cancel_reason in CANCEL_REASONS:
        order.cancel_reason = cancel_reason
    session.add(
        OrderStatusLog(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            actor_telegram_id=actor_telegram_id,
        )
    )
    await session.commit()
    return order
