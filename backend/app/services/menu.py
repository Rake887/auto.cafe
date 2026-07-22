from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import Branch, Category, Dish, Point
from app.schemas.menu import CategoryOut, DishOut, MenuResponse


def is_visible_at(
    start: time | None, end: time | None, now: time
) -> bool:
    """Попадает ли момент в окно.

    Обе границы пустые — окна нет, попадает всегда. Окно, перевёрнутое через
    полночь (22:00–02:00), считается как объединение двух отрезков, иначе
    ночное меню не показалось бы никогда.

    Используется дважды: часы показа категории и часы приёма заказов
    (см. closed_reason в services/orders.py).
    """
    if start is None and end is None:
        return True
    if start is None:
        return now < end
    if end is None:
        return now >= start
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def _pick(ru: str | None, kk: str | None, lang: str) -> str | None:
    """Казахская версия, если она заполнена, иначе русская.

    Меню переводят постепенно, и блюдо без перевода должно остаться видимым,
    а не превратиться в пустую строку.
    """
    return (kk or ru) if lang == "kk" else ru


async def get_menu_by_token(
    session: AsyncSession, token: str, lang: str = "ru"
) -> MenuResponse | None:
    """Собрать полное меню филиала по QR-токену стола. None — токен не найден."""
    point = await session.scalar(
        select(Point)
        # снятый стол не должен открываться: наклейку могли унести с собой
        .where(Point.token == token, Point.is_archived.is_(False))
        .options(selectinload(Point.branch))
    )
    if point is None:
        return None

    categories = (
        await session.scalars(
            select(Category)
            .where(
                Category.branch_id == point.branch_id,
                Category.is_archived.is_(False),
            )
            .order_by(Category.sort_order, Category.id)
            .options(
                selectinload(
                    Category.dishes.and_(
                        # в стоп-листе и удалённые гостю не показываем
                        Dish.is_active.is_(True),
                        Dish.is_archived.is_(False),
                    )
                )
            )
        )
    ).all()

    # Часы показа считаем по времени заведения: в базе всё в UTC, и без
    # пересчёта бизнес-ланч в Таразе открывался бы в семь утра.
    settings = get_settings()
    now_local = datetime.now(ZoneInfo(settings.display_timezone))

    # импорт здесь: services.orders уже импортирует нас ради is_visible_at,
    # на уровне модуля это дало бы кольцо
    from app.services.orders import closed_reason

    reason = closed_reason(point.branch, now_local)

    return MenuResponse(
        branch_name=point.branch.name,
        point_label=point.label,
        menu_disclaimer=point.branch.menu_disclaimer,
        accepting_orders=reason is None,
        closed_reason=reason,
        geo_check_enabled=bool(
            point.branch.lat is not None
            and point.branch.lon is not None
            and point.branch.geo_radius_m
        ),
        categories=[
            CategoryOut(
                id=c.id,
                name=_pick(c.name, c.name_kk, lang) or c.name,
                dishes=[
                    DishOut(
                        id=d.id,
                        name=_pick(d.name, d.name_kk, lang) or d.name,
                        description=_pick(d.description, d.description_kk, lang),
                        price=d.price,
                        image_url=d.image_url,
                        is_veg=d.is_veg,
                        is_spicy=d.is_spicy,
                        is_hit=d.is_hit,
                        is_chef=d.is_chef,
                        allergens=d.allergens,
                    )
                    for d in c.dishes
                ],
            )
            for c in categories
            if is_visible_at(c.available_from, c.available_to, now_local.time())
        ],
    )
