from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class AdminDishOut(BaseModel):
    """Блюдо глазами владельца — со скрытыми полями, которых гость не видит."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_kk: str | None
    description: str | None
    description_kk: str | None
    price: int
    # во сколько блюдо обходится заведению; None — ещё не считали
    cost_price: int | None
    image_url: str | None
    is_active: bool
    sort_order: int
    is_veg: bool
    is_spicy: bool
    is_hit: bool
    is_chef: bool
    allergens: str | None


class AdminCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_kk: str | None
    sort_order: int
    # часы показа гостю; обе пустые — категория видна всегда
    available_from: time | None
    available_to: time | None
    dishes: list[AdminDishOut]


class AdminMenuOut(BaseModel):
    branch_name: str
    menu_disclaimer: str | None
    categories: list[AdminCategoryOut]


class ImportRowOut(BaseModel):
    line: int
    category: str
    name: str
    price: int
    # create — блюда ещё нет, update — цена и описание перезапишутся
    action: str


class ImportReportOut(BaseModel):
    """Что произойдёт (или произошло) при заливке таблицы."""

    applied: bool
    to_create: int
    to_update: int
    new_categories: list[str]
    errors: list[str]
    preview: list[ImportRowOut]


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    name_kk: str | None = Field(default=None, max_length=255)
    # часы показа; чтобы снять расписание, шлём clear_schedule
    available_from: time | None = None
    available_to: time | None = None
    # None-поля в PATCH означают «не трогать», поэтому для сброса расписания
    # нужен отдельный признак — иначе снять его было бы нечем
    clear_schedule: bool = False


class DishIn(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=255)
    # казахские версии; пусто — гостю на kk показываем русские
    name_kk: str | None = Field(default=None, max_length=255)
    description_kk: str | None = Field(default=None, max_length=500)
    price: int = Field(gt=0, le=10_000_000)
    cost_price: int | None = Field(default=None, ge=0, le=10_000_000)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    is_veg: bool = False
    is_spicy: bool = False
    is_hit: bool = False
    is_chef: bool = False
    allergens: str | None = Field(default=None, max_length=300)


class DishPatch(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    # пустая строка здесь значит «убрать перевод», поэтому она не равна None
    name_kk: str | None = Field(default=None, max_length=255)
    description_kk: str | None = Field(default=None, max_length=500)
    price: int | None = Field(default=None, gt=0, le=10_000_000)
    cost_price: int | None = Field(default=None, ge=0, le=10_000_000)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    # стоп-лист: блюдо закончилось
    is_active: bool | None = None
    is_veg: bool | None = None
    is_spicy: bool | None = None
    is_hit: bool | None = None
    is_chef: bool | None = None
    allergens: str | None = Field(default=None, max_length=300)


class BranchPatch(BaseModel):
    """Настройки заведения, которые видит гость."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    menu_disclaimer: str | None = Field(default=None, max_length=1000)
    review_url: str | None = Field(default=None, max_length=500)
    # часы приёма заказов; чтобы снять расписание, шлём clear_hours
    opens_at: time | None = None
    closes_at: time | None = None
    clear_hours: bool = False
    # стоп-кран: выключить приём заказов, не трогая расписание
    accepting_orders: bool | None = None
    # координаты зала и радиус для метки «заказ вне зала»
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    geo_radius_m: int | None = Field(default=None, ge=10, le=5000)
    clear_geo: bool = False
    # публичный IP заведения; пустая строка — убрать
    trusted_ip: str | None = Field(default=None, max_length=45)


class PlaceLinkIn(BaseModel):
    """Ссылка на карточку заведения в 2ГИС, Яндексе или Google."""

    url: str = Field(min_length=1, max_length=2000)


class PlaceLinkOut(BaseModel):
    lat: float
    lon: float
    # какой сервис опознали — владельцу спокойнее, когда видно источник
    source: str
    # ссылка «посмотреть точку на карте»: перепутанный порядок чисел ловится
    # только глазами, поэтому проверка обязательна
    verify_url: str


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    menu_disclaimer: str | None
    review_url: str | None
    opens_at: time | None
    closes_at: time | None
    accepting_orders: bool
    lat: float | None
    lon: float | None
    geo_radius_m: int | None
    trusted_ip: str | None
