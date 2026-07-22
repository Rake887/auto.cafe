"""Сидинг и обновление демо-данных: кафе, столы с QR-токенами, меню.

Запуск: python -m app.seed
Повторный запуск обновляет категории, блюда и устанавливает качественные фото.
"""

import asyncio
import secrets

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import async_session_factory, engine
from app.models import AdminUser, Branch, Category, Dish, Organization, Point, Zone
from app.services.auth import hash_password

# (название, цена в тенге, описание, ссылка на качественное фото)
MENU = {
    "Горячие блюда": [
        (
            "Плов по-тараски",
            2500,
            "Баранина, жёлтая морковь, нут, казан. Порция 350 г",
            "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Шашлык из баранины",
            3100,
            "Сочные кусочки маринованной баранины на углях с красным луком и зеленью",
            "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Лагман уйгурский",
            2200,
            "Тянутая лапша ручной работы, говядина, болгарский перец, сельдерей",
            "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Манты с мясом (5 шт.)",
            1800,
            "Рубленая баранина с луком, сочное тонкое тесто ручной лепки",
            "https://images.unsplash.com/photo-1541696432-82c6da8ce7bf?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Бешбармак по-казахски",
            3600,
            "Отварная конина и сочная говядина с тонким кеспе и соусом созпа",
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Куырдак из баранины",
            2600,
            "Традиционное сочное жаркое из баранины с картофелем и специями",
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Стейк Рибай с овощами",
            4500,
            "Стейк из мраморной говядины средней прожарки с овощами гриль",
            "https://images.unsplash.com/photo-1600891964092-4316c288032e?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Шурпа с бараниной",
            1900,
            "Наваристый традиционный бульон с крупным куском баранины и овощами",
            "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    "Закуски": [
        (
            "Чебуреки сочные (2 шт.)",
            1400,
            "Хрустящие золотистые чебуреки с начинкой из рубленой говядины",
            "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Сырные палочки Моцарелла",
            1600,
            "Обжаренный сыр моцарелла в хрустящей панировке с ягодным соусом",
            "https://images.unsplash.com/photo-1531749668029-2db88e4276c7?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Картофель по-деревенски",
            1100,
            "Запечённые дольки картофеля с чесноком, укропом и соусом тар-тар",
            "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Чесночные гренки с соусом",
            950,
            "Ржаные гренки с чесночным маслом и пикантным фирменным соусом",
            "https://images.unsplash.com/photo-1509722747041-616f39b57569?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    "Салаты": [
        (
            "Салат «Ачичук»",
            1200,
            "Свежие томаты, красный лук, зелень и острого перца чили",
            "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Цезарь с цыпленком",
            2100,
            "Сочное филе на гриле, свежий ромэн, пармезан и фирменный соус",
            "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Салат с авокадо и креветками",
            2700,
            "Тигровые креветки, спелый авокадо, черри и микс-салат",
            "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Греческий салат",
            1600,
            "Свежие овощи, сыр фета, маслины Каламата и оливковое масло extra virgin",
            "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Овощной салат с зеленью",
            1100,
            "Огурцы, редис, хрустящие томаты и домашняя сметана",
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    "Напитки": [
        (
            "Чай фирменный с яблоком",
            950,
            "Ароматный чайник 1 л с кусочками свежих яблок и корицей",
            "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Капучино",
            1100,
            "Эспрессо из 100% арабики и шелковистая молочная пенка, 300 мл",
            "https://images.unsplash.com/photo-1534778101976-62847782c213?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Латте Макиато",
            1300,
            "Нежный трехслойный кофейный напиток с ванильным оттенком, 350 мл",
            "https://images.unsplash.com/photo-1570968915860-54d5c301fa9f?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Американо",
            900,
            "Двойной эспрессо из свежеобжаренного зерна, 250 мл",
            "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Лимонад «Малина-Маракуйя»",
            1400,
            "Домашний освежающий лимонад со свежими ягодами и соком маракуйи, 500 мл",
            "https://images.unsplash.com/photo-1621263764928-df1444c5e859?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Морс клюквенный",
            700,
            "Домашний натуральный морс из дикой клюквы, не сладкий",
            "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Свежевыжатый апельсиновый сок",
            1500,
            "100% фреш из отборных сочных апельсинов, 300 мл",
            "https://images.unsplash.com/photo-1613478223719-2ab802602423?auto=format&fit=crop&w=800&q=80",
        ),
    ],
    "Десерты": [
        (
            "Чизкейк Сан-Себастьян",
            1800,
            "Нежный опалённый баскский чизкейк с кремовой текстурой",
            "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Тирамису классический",
            1700,
            "Итальянский десерт с сыром маскарпоне и печеньем савоярди",
            "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Медовик домашний",
            1300,
            "Десять нежнейших коржей со сметанно-медовым кремом",
            "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Фисташковый рулет с малиной",
            1900,
            "Воздушный меренговый рулет с фисташковым кремом и свежей малиной",
            "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=800&q=80",
        ),
        (
            "Чак-чак медовый",
            900,
            "Хрустящее золотистое тесто в натуральном медовом сиропе, 150 г",
            "https://images.unsplash.com/photo-1587314168485-3236d6710814?auto=format&fit=crop&w=800&q=80",
        ),
    ],
}


async def seed() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        existing = await session.scalar(
            select(Organization).where(Organization.id == settings.demo_organization_id)
        )
        if existing is None:
            org = Organization(id=settings.demo_organization_id, name="Demo Cafe Group")
            branch = Branch(organization=org, name="Кафе «Тараз»")
            zone = Zone(branch=branch, name="Основной зал", sort_order=0)
            session.add_all([org, branch, zone])

            points = [
                Point(
                    branch=branch,
                    zone=zone,
                    label=f"Стол {n}",
                    token=(
                        settings.demo_token
                        if n == 1 and settings.demo_token
                        else secrets.token_urlsafe(12)
                    ),
                )
                for n in range(1, 6)
            ]
            session.add_all(points)
            await session.commit()
            print("Организация, зона и столы созданы.")
        else:
            branch = await session.scalar(
                select(Branch).where(Branch.organization_id == existing.id)
            )

        if not branch:
            print("Филиал не найден!")
            return

        # Создаём или обновляем демо-администратора (admin / adminpassword123)
        admin_user = await session.scalar(
            select(AdminUser).where(AdminUser.login == "admin")
        )
        if admin_user is None:
            demo_admin = AdminUser(
                login="admin",
                password_hash=hash_password("adminpassword123"),
                full_name="Администратор Кафе",
            )
            session.add(demo_admin)
        else:
            admin_user.password_hash = hash_password("adminpassword123")
            admin_user.failed_attempts = 0
            admin_user.locked_until = None
        await session.commit()
        print("Демо-администратор готов (логин: admin / пароль: adminpassword123).")

        # Деактивируем все старые записи блюд с картинками picsum
        picsum_dishes = (
            await session.scalars(
                select(Dish).where(Dish.image_url.like("%picsum.photos%"))
            )
        ).all()
        for d in picsum_dishes:
            d.is_active = False

        await session.flush()

        # Обновляем или создаем категории и блюда с красивыми качественными фото
        existing_cats = (
            await session.scalars(select(Category).where(Category.branch_id == branch.id))
        ).all()
        cat_map = {c.name: c for c in existing_cats}

        for sort_order, (cat_name, dishes) in enumerate(MENU.items()):
            category = cat_map.get(cat_name)
            if not category:
                category = Category(branch=branch, name=cat_name, sort_order=sort_order)
                session.add(category)
                await session.flush()
                cat_map[cat_name] = category
            else:
                category.sort_order = sort_order

            existing_dishes = (
                await session.scalars(select(Dish).where(Dish.category_id == category.id))
            ).all()
            dish_map = {d.name: d for d in existing_dishes}

            for i, (dish_name, price, description, image_url) in enumerate(dishes):
                dish = dish_map.get(dish_name)
                if not dish:
                    dish = Dish(
                        category=category,
                        name=dish_name,
                        description=description,
                        price=price,
                        image_url=image_url,
                        is_active=True,
                        sort_order=i,
                    )
                    session.add(dish)
                else:
                    dish.price = price
                    dish.description = description
                    dish.image_url = image_url
                    dish.is_active = True
                    dish.sort_order = i

        await session.commit()
        print("Меню и качественные фотографии блюд успешно обновлены!")
        await print_tokens(session)


async def print_tokens(session) -> None:
    rows = (await session.execute(select(Point.label, Point.token))).all()
    print("\nТокены столов (для GET /m/{token}):")
    for label, token in rows:
        print(f"  {label}: {token}")


async def _main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
