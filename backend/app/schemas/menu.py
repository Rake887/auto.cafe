from pydantic import BaseModel, ConfigDict


class DishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: int
    image_url: str | None
    # Метки и аллергены задаёт владелец: гость читает их как утверждение
    # заведения, а не как догадку системы по словам в описании
    is_veg: bool
    is_spicy: bool
    is_hit: bool
    is_chef: bool
    allergens: str | None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    dishes: list[DishOut]


class MenuResponse(BaseModel):
    """Ответ GET /m/{token} — всё меню одним запросом."""

    branch_name: str
    point_label: str
    categories: list[CategoryOut]
    # предупреждение об аллергенах внизу меню; None — заведение не заполнило
    menu_disclaimer: str | None
    # Принимает ли заведение заказы прямо сейчас. Гость должен узнать об этом
    # до того, как соберёт корзину, а не после нажатия «Оформить».
    accepting_orders: bool
    closed_reason: str | None
    # Заведение задало координаты и радиус — значит геопозиция гостя на
    # что-то влияет. Если нет, спрашивать разрешение незачем: это был бы
    # запрос ради запроса, а такие приучают отказывать не глядя.
    geo_check_enabled: bool
