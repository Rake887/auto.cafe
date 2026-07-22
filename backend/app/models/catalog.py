from datetime import date, time
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))

    branches: Mapped[list["Branch"]] = relationship(back_populates="organization")


class Branch(Base):
    __tablename__ = "branch"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))
    name: Mapped[str] = mapped_column(String(255))
    # Предупреждение об аллергенах внизу гостевого меню. Обычный текст:
    # HTML из поля ввода в разметку не вставляем — это XSS.
    menu_disclaimer: Mapped[str | None] = mapped_column(String(1000))
    # Куда звать довольного гостя оставить публичный отзыв (2GIS, Google, Яндекс)
    review_url: Mapped[str | None] = mapped_column(String(500))

    # Часы приёма заказов. Обе пустые — принимаем круглосуточно. Время местное,
    # в поясе заведения; окно через полночь (22:00–02:00) считается корректно.
    opens_at: Mapped[time | None] = mapped_column(Time)
    closes_at: Mapped[time | None] = mapped_column(Time)
    # Стоп-кран: владелец выключает приём заказов, не трогая расписание
    accepting_orders: Mapped[bool] = mapped_column(default=True)

    # Координаты зала и радиус: заказ извне не блокируем, но помечаем.
    # Пусто — проверка выключена.
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    geo_radius_m: Mapped[int | None] = mapped_column()
    # Публичный IP заведения: гость на его Wi-Fi заведомо в зале. Самый
    # надёжный из доступных признаков присутствия и единственный, который
    # гость не может подделать со стороны. Пусто — признак не используется.
    trusted_ip: Mapped[str | None] = mapped_column(String(45))

    organization: Mapped[Organization] = relationship(back_populates="branches")
    points: Mapped[list["Point"]] = relationship(back_populates="branch")
    categories: Mapped[list["Category"]] = relationship(back_populates="branch")
    zones: Mapped[list["Zone"]] = relationship(back_populates="branch")


class Zone(Base):
    """Зал, терраса, VIP — группа столов со своей нумерацией заказов."""

    __tablename__ = "zone"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0)
    # Счётчик заказов внутри зоны и день, за который он идёт: «Терраса №14»
    # понятнее сквозного #613, а к утру нумерация начинается заново
    order_counter: Mapped[int] = mapped_column(default=0)
    counter_day: Mapped[date | None] = mapped_column(Date)

    branch: Mapped[Branch] = relationship(back_populates="zones")
    points: Mapped[list["Point"]] = relationship(back_populates="zone")


class Point(Base):
    """Точка заказа — стол/кабинка, на которую наклеен QR."""

    __tablename__ = "point"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zone.id"))
    label: Mapped[str] = mapped_column(String(100))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Снятый стол: на него ссылаются прошлые заказы и вызовы официанта,
    # поэтому убираем из списков, а строку оставляем
    is_archived: Mapped[bool] = mapped_column(default=False)

    branch: Mapped[Branch] = relationship(back_populates="points")
    zone: Mapped[Zone] = relationship(back_populates="points")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    name: Mapped[str] = mapped_column(String(255))
    # Название по-казахски; пусто — показываем русское
    name_kk: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(default=0)
    # «Удаление» категории — архивирование: её блюда есть в истории заказов
    is_archived: Mapped[bool] = mapped_column(default=False)
    # Часы показа гостю: бизнес-ланч с 12 до 16, завтраки до 11. Оба пустые —
    # категория видна всегда. Время местное, в поясе заведения.
    available_from: Mapped[time | None] = mapped_column(Time)
    available_to: Mapped[time | None] = mapped_column(Time)

    branch: Mapped[Branch] = relationship(back_populates="categories")
    dishes: Mapped[list["Dish"]] = relationship(
        back_populates="category", order_by="Dish.sort_order, Dish.id"
    )


class Dish(Base):
    __tablename__ = "dish"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    name: Mapped[str] = mapped_column(String(255))
    # Состав или пара слов о блюде — гостю мало одного названия
    description: Mapped[str | None] = mapped_column(String(500))
    # Казахские версии; пусто — гостю на kk показываем русские.
    # Заведение переводит меню постепенно, и полупустой перевод не должен
    # оставлять в меню дыры.
    name_kk: Mapped[str | None] = mapped_column(String(255))
    description_kk: Mapped[str | None] = mapped_column(String(500))
    # Цена в тенге, целое число — тиыны в общепите не используются
    price: Mapped[int] = mapped_column()
    # Во сколько блюдо обходится заведению. None — владелец ещё не считал,
    # и тогда прибыль по нему честнее не показывать вовсе, чем показать нулём.
    cost_price: Mapped[int | None] = mapped_column()
    image_url: Mapped[str | None] = mapped_column(String(500))
    # Метки для гостя. Ставит владелец: угадывать «вегетарианское» по словам
    # в описании нельзя — цена ошибки здесь чужое здоровье.
    is_veg: Mapped[bool] = mapped_column(default=False)
    is_spicy: Mapped[bool] = mapped_column(default=False)
    is_hit: Mapped[bool] = mapped_column(default=False)
    is_chef: Mapped[bool] = mapped_column(default=False)
    # Аллергены свободным текстом: «орехи, молоко, глютен»
    allergens: Mapped[str | None] = mapped_column(String(300))
    # Стоп-лист: блюдо временно закончилось, гость его не видит
    is_active: Mapped[bool] = mapped_column(default=True)
    # Удалённое навсегда. Физически строку не трогаем — на неё ссылаются
    # позиции заказов, а история выручки должна оставаться правдивой.
    is_archived: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)

    category: Mapped[Category] = relationship(back_populates="dishes")
