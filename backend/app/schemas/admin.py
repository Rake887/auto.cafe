from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import OrderStatus


class TotalsOut(BaseModel):
    """Сводка по заказам за период. Отменённые в деньгах не учитываем."""

    orders: int
    revenue: int
    average_check: int
    # заказы, ещё не дошедшие до «обслужен» — что сейчас в работе
    in_progress: int
    cancelled: int
    # заказы, которые никто не взял в работу: кухня не смотрит в чат.
    # Именно из-за них суммы по персоналу меньше общей выручки.
    untouched: int
    untouched_revenue: int
    # среднее время от оформления до подачи, в минутах; None — ещё нет данных
    avg_minutes_to_served: float | None
    # Доля себестоимости в выручке по тем позициям, где она известна.
    # None — себестоимость не заполнена ни у одного проданного блюда.
    food_cost_percent: float | None
    # Выручка минус себестоимость по тем же позициям
    profit: int
    # Какой процент проданных порций попал в расчёт: по половине меню
    # фудкост нельзя показывать как точную цифру
    costed_share: int


class DishStatOut(BaseModel):
    name: str
    qty: int
    revenue: int
    # None — на момент заказа себестоимость не знали
    profit: int | None = None


class StaffStatOut(BaseModel):
    """Кто и сколько заказов провёл через свою кнопку в боте."""

    name: str
    role: str | None
    orders: int
    revenue: int


class ZoneOut(BaseModel):
    """Зал, терраса, VIP — группа столов со своей нумерацией заказов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ZonePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class PointOut(BaseModel):
    """Стол и ссылка, которая зашита в его QR-код."""

    id: int
    label: str
    token: str
    zone_id: int
    zone_name: str
    # None, если публичный адрес неизвестен (туннель не поднят)
    menu_url: str | None


class PointsResponse(BaseModel):
    site_url: str | None
    zones: list[ZoneOut]
    points: list[PointOut]


class PointIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    # None — положить в первую зону: у заведения без террасы её выбирать незачем
    zone_id: int | None = None


class PointPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    zone_id: int | None = None


class OpenCallOut(BaseModel):
    """Незакрытый вызов официанта — строка в сводке «сейчас в зале»."""

    id: int
    point_label: str
    zone_name: str
    comment: str | None
    waiting_seconds: int
    # бот уже дёрнул чат повторно — значит, вызов просрочен по SLA
    escalated: bool


class OpenVisitOut(BaseModel):
    """Открытый визит: сколько заказов и на какую сумму ждёт счёт."""

    id: int
    point_label: str
    zone_name: str
    orders: int
    total: int
    opened_at: datetime
    # хотя бы один заказ пришёл с координатами вне зала
    has_remote: bool
    # за стол поручились (автоматически или кнопкой в чате); пока нет —
    # кухня не начинает готовить
    confirmed: bool


class PulseOut(BaseModel):
    """Что горит прямо сейчас. Считается дёшево — экран опрашивает часто."""

    orders_new: int
    orders_cooking: int
    orders_ready: int
    # сколько минут ждёт самый старый непринятый заказ; None — таких нет
    oldest_new_minutes: int | None
    open_calls: list[OpenCallOut]
    unresolved_reviews: int
    # столы, по которым ещё не закрыли счёт
    open_visits: list[OpenVisitOut]


class AdminServiceCallOut(BaseModel):
    id: int
    created_at: datetime
    point_label: str
    zone_name: str
    comment: str | None
    resolved_at: datetime | None
    waiting_seconds: int
    escalated: bool
    # кто нажал «Иду»; None — закрыт из кабинета или ещё открыт
    taken_by: str | None


class AdminOrderItemOut(BaseModel):
    """Позиция заказа по ценам на момент оформления."""

    name: str
    qty: int
    price: int
    # блюдо кончилось, официант вычеркнул его из заказа — в total не входит
    unavailable: bool = False


class AdminOrderOut(BaseModel):
    id: int
    # человеческий номер: «Терраса №14», у старых заказов — «#61»
    number: str
    created_at: datetime
    status: OrderStatus
    point_label: str
    # None у заказов, оформленных до появления зон
    zone_name: str | None
    total: int
    comment: str | None
    items: list[AdminOrderItemOut]
    # телефон гостя был далеко от заведения — повод посмотреть на стол
    is_remote: bool
    # кто принял на кухне и кто отнёс; None — до этого шага ещё не дошло
    cooked_by: str | None
    served_by: str | None
    # человеческая причина отмены. None — отменили из кабинета или причину
    # не выбирали; сама отмена видна по status
    cancel_reason: str | None


class AdminReviewOut(BaseModel):
    """Оценка гостя глазами владельца — с привязкой к конкретному заказу."""

    id: int
    created_at: datetime
    rating: int
    comment: str | None
    order_number: str
    point_label: str
    order_total: int
    # заполнено — владелец отметил, что разобрался
    resolved_at: datetime | None


class ZoneStatOut(BaseModel):
    """Как торгует зал: терраса летом может обгонять основной зал."""

    name: str
    orders: int
    revenue: int
    average_check: int


class BucketOut(BaseModel):
    """Заказы и выручка в одном срезе — часе суток или дне недели."""

    label: str
    orders: int
    revenue: int


class AdminStats(BaseModel):
    period: str
    branch_name: str
    totals: TotalsOut
    top_dishes: list[DishStatOut]
    # то же меню, но отсортированное по заработку, а не по популярности
    top_profit: list[DishStatOut]
    waiters: list[StaffStatOut]
    cooks: list[StaffStatOut]
    # только часы, в которые вообще были заказы — пустые 4 утра не нужны
    by_hour: list[BucketOut]
    by_weekday: list[BucketOut]
    by_zone: list[ZoneStatOut]
    # средняя оценка гостей; None — за период не оценивали
    rating_avg: float | None
    rating_count: int
