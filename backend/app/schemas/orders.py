from datetime import datetime

from pydantic import BaseModel, Field

from app.models import OrderStatus


class OrderItemIn(BaseModel):
    dish_id: int
    qty: int = Field(ge=1, le=50)


class OrderCreate(BaseModel):
    """Тело POST /orders. Цены клиент НЕ присылает — сервер берёт их из БД."""

    point_token: str
    client_request_id: str = Field(min_length=8, max_length=64)
    items: list[OrderItemIn] = Field(min_length=1)
    # пожелание к заказу целиком: «без лука», «принести приборы»
    comment: str | None = Field(default=None, max_length=300)
    # Координаты гостя, если браузер их дал. Необязательны: отказ в доступе
    # к геолокации не должен мешать заказать — часть гостей всегда откажет.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class OrderCreated(BaseModel):
    order_id: int
    status: OrderStatus
    total: int


class OrderItemOut(BaseModel):
    dish_name: str
    qty: int
    price: int
    # Официант отметил, что блюдо кончилось. Позиция остаётся в списке —
    # гость должен увидеть, чего именно не будет, а не гадать, почему сумма
    # стала меньше. В total такая позиция уже не входит.
    unavailable: bool = False


class VisitOrderOut(BaseModel):
    """Соседний заказ того же стола — без состава, только этап и сумма.

    Состав не отдаём намеренно: за столом могут сидеть чужие друг другу люди
    (гость сканирует QR там, где до него сидела другая компания), а счёт всё
    равно общий — для него достаточно суммы.
    """

    id: int
    number: str
    status: OrderStatus
    total: int


class VisitOut(BaseModel):
    """Визит стола: все заказы до закрытия счёта.

    Приходит только когда заказов больше одного — на первом показывать
    «итого по столу», равное самому заказу, незачем.
    """

    point_label: str
    orders: list[VisitOrderOut]
    total: int


class OrderOut(BaseModel):
    """Ответ GET /orders/{id} — для поллинга статуса с фронта."""

    id: int
    # номер для людей: «Терраса №14». Гость называет его официанту, поэтому
    # он должен быть коротким, а не сквозным идентификатором базы
    number: str
    status: OrderStatus
    created_at: datetime
    total: int
    comment: str | None
    # Имена сотрудников, которые ведут заказ. Гость видит, что за заказом стоят
    # люди, — при обезличенном QR-заказе чаевые падают почти вчетверо.
    cooked_by: str | None
    served_by: str | None
    items: list[OrderItemOut]
    # Стол дозаказывал: этот заказ не единственный за визит. None — заказ
    # один, и гостю нечего подвязывать.
    visit: VisitOut | None = None
