import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OrderStatus(str, enum.Enum):
    new = "new"
    accepted = "accepted"
    ready = "ready"
    served = "served"
    cancelled = "cancelled"


class TableSession(Base):
    """Визит за столом: все заказы одной компании до закрытия счёта.

    Гости заказывают с трёх телефонов — это три заказа, но счёт официант
    приносит один. Визит и есть та сущность, по которой считается общая сумма.
    """

    __tablename__ = "table_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    point_id: Mapped[int] = mapped_column(ForeignKey("point.id"), index=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # заполняется, когда официант закрыл счёт или визит протух по времени
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Кто-то поручился, что за столом действительно сидят: либо это сделали
    # автоматически признаки присутствия (Wi-Fi заведения, координаты), либо
    # официант нажал кнопку в чате. Пока пусто — кухня не начинает готовить.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    orders: Mapped[list["Order"]] = relationship(back_populates="session")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    point_id: Mapped[int] = mapped_column(ForeignKey("point.id"))
    # Зона и номер внутри неё на момент заказа — снапшот: стол могут перевести
    # на террасу, и тогда прошлые заказы не должны переехать вместе с ним
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zone.id"))
    zone_seq: Mapped[int | None] = mapped_column()
    # Визит, в который попал заказ. None у заказов до появления визитов.
    session_id: Mapped[int | None] = mapped_column(ForeignKey("table_session.id"))
    # Гость дал координаты, и они дальше радиуса зала. Заказ всё равно приняли —
    # это метка для официанта, а не блокировка: GPS в помещении врёт.
    is_remote: Mapped[bool] = mapped_column(default=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.new
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # UUID от клиента: защита от дублей при повторном тапе «Оформить заказ»
    client_request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # id сообщения бота в группе — чтобы редактировать его при смене статуса
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    # Пожелание гостя целиком к заказу: «без лука», «побольше соуса».
    # Модификаторы блюд в MVP не делаем, это компромисс вместо них.
    comment: Mapped[str | None] = mapped_column(String(300))
    # Когда бот напомнил про заказ, который никто не взял в работу.
    # Заполнено — повторно не напоминаем.
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Почему заказ отменили. Владельцу важна разница: «стол пуст» — это
    # выброшенная еда, «гость передумал» до готовки — потерь нет.
    cancel_reason: Mapped[str | None] = mapped_column(String(32))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin"
    )
    status_logs: Mapped[list["OrderStatusLog"]] = relationship(back_populates="order")
    session: Mapped["TableSession | None"] = relationship(back_populates="orders")

    @property
    def total(self) -> int:
        """Сумма к оплате. За то, чего не оказалось, гость не платит."""
        return sum(
            i.price_snapshot * i.qty for i in self.items if i.unavailable_at is None
        )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dish.id"))
    qty: Mapped[int] = mapped_column()
    # Снапшоты цены и названия на момент заказа — история не должна «ехать»
    # при последующем изменении блюда
    price_snapshot: Mapped[int] = mapped_column()
    dish_name_snapshot: Mapped[str] = mapped_column(String(255))
    # Себестоимость на тот же момент. None — на момент заказа её не считали,
    # такие позиции из расчёта прибыли исключаются
    cost_snapshot: Mapped[int | None] = mapped_column()
    # Когда официант отметил, что блюдо кончилось. Позицию не удаляем: гостю
    # надо показать, чего именно он не дождётся, а владельцу — что заведение
    # не смогло отдать. В деньги и статистику такая позиция не идёт.
    unavailable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusLog(Base):
    __tablename__ = "order_status_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[OrderStatus | None] = mapped_column(
        Enum(OrderStatus, name="order_status")
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status")
    )
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped[Order] = relationship(back_populates="status_logs")


class ServiceCall(Base):
    """Гость позвал официанта кнопкой в меню."""

    __tablename__ = "service_call"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    point_id: Mapped[int] = mapped_column(ForeignKey("point.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # заполняется, когда официант нажал «Иду»
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    # что нужно гостю: «принести счёт», «пролили чай»
    comment: Mapped[str | None] = mapped_column(String(300))
    # Когда бот повторно дёрнул чат из-за просроченного вызова.
    # Заполнено — второй раз не эскалируем.
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base):
    """Оценка гостя после подачи заказа.

    Один заказ — одна оценка (unique на order_id): иначе выставленную звезду
    можно было бы переписать повторной отправкой.
    """

    __tablename__ = "review"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    rating: Mapped[int] = mapped_column()
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # когда владелец отметил, что разобрался с жалобой
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
