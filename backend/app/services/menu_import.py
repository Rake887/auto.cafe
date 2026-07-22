"""Массовая заливка меню из таблицы.

У заведения прайс обычно уже есть файлом, вбивать шестьдесят позиций руками
никто не станет. Разбор устроен под то, что реально приходит от владельцев:
файл из русского Excel — точка с запятой вместо запятой и cp1251 вместо UTF-8.
"""

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Dish

COLUMNS = ("category", "name", "price", "description", "image_url")
TEMPLATE = (
    "category,name,price,description,image_url\r\n"
    "Горячие блюда,Плов,2500,Баранина и жёлтая морковь,\r\n"
    "Напитки,Чай,800,Чайник 1 л,\r\n"
)


class ImportBroken(Exception):
    """Файл не удалось разобрать целиком."""


@dataclass
class ImportRow:
    line: int
    category: str
    name: str
    price: int
    description: str | None
    image_url: str | None
    # что произойдёт при применении: create | update
    action: str = "create"


@dataclass
class ImportReport:
    rows: list[ImportRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    new_categories: list[str] = field(default_factory=list)

    @property
    def to_create(self) -> int:
        return sum(1 for r in self.rows if r.action == "create")

    @property
    def to_update(self) -> int:
        return sum(1 for r in self.rows if r.action == "update")


def decode(raw: bytes) -> str:
    """UTF-8, иначе cp1251 — как сохраняет русский Excel."""
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportBroken("Не удалось определить кодировку файла")


def _reader(text: str) -> csv.DictReader:
    sample = text.split("\n", 1)[0]
    # Excel в русской локали разделяет точкой с запятой
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return csv.DictReader(io.StringIO(text), delimiter=delimiter)


async def parse(session: AsyncSession, branch_id: int, raw: bytes) -> ImportReport:
    """Разобрать файл и рассказать, что произойдёт. Ничего не меняет."""
    reader = _reader(decode(raw))
    if reader.fieldnames is None:
        raise ImportBroken("Файл пустой")

    headers = {(h or "").strip().lower() for h in reader.fieldnames}
    missing = {"category", "name", "price"} - headers
    if missing:
        raise ImportBroken(
            "В заголовке не хватает колонок: " + ", ".join(sorted(missing))
        )

    existing = await _existing_dishes(session, branch_id)
    known_categories = {
        name.lower() for name, _ in await _categories(session, branch_id)
    }

    report = ImportReport()
    seen: set[tuple[str, str]] = set()
    for line, row in enumerate(reader, start=2):
        values = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        category = values.get("category", "")
        name = values.get("name", "")
        raw_price = values.get("price", "").replace(" ", "").replace("\xa0", "")

        if not category or not name:
            report.errors.append(f"строка {line}: пустая категория или название")
            continue
        try:
            price = int(float(raw_price.replace(",", ".")))
        except ValueError:
            report.errors.append(f"строка {line}: цена «{raw_price}» не число")
            continue
        if price <= 0:
            report.errors.append(f"строка {line}: цена должна быть больше нуля")
            continue

        key = (category.lower(), name.lower())
        if key in seen:
            report.errors.append(f"строка {line}: «{name}» повторяется в файле")
            continue
        seen.add(key)

        if category.lower() not in known_categories:
            known_categories.add(category.lower())
            report.new_categories.append(category)

        report.rows.append(
            ImportRow(
                line=line,
                category=category,
                name=name,
                price=price,
                description=values.get("description") or None,
                image_url=values.get("image_url") or None,
                action="update" if key in existing else "create",
            )
        )
    return report


async def apply(session: AsyncSession, branch_id: int, report: ImportReport) -> None:
    """Применить разобранный файл: создать недостающее, обновить совпавшее."""
    categories = {name.lower(): obj_id for name, obj_id in await _categories(session, branch_id)}
    existing = await _existing_dishes(session, branch_id)

    last_sort = await session.scalar(
        select(func.coalesce(func.max(Category.sort_order), 0)).where(
            Category.branch_id == branch_id
        )
    )

    for row in report.rows:
        category_id = categories.get(row.category.lower())
        if category_id is None:
            last_sort += 1
            category = Category(
                branch_id=branch_id, name=row.category, sort_order=last_sort
            )
            session.add(category)
            await session.flush()
            category_id = category.id
            categories[row.category.lower()] = category_id

        dish_id = existing.get((row.category.lower(), row.name.lower()))
        if dish_id is not None:
            dish = await session.get(Dish, dish_id)
            dish.price = row.price
            if row.description:
                dish.description = row.description
            if row.image_url:
                dish.image_url = row.image_url
            dish.is_archived = False
        else:
            position = await session.scalar(
                select(func.coalesce(func.max(Dish.sort_order), 0)).where(
                    Dish.category_id == category_id
                )
            )
            session.add(
                Dish(
                    category_id=category_id,
                    name=row.name,
                    price=row.price,
                    description=row.description,
                    image_url=row.image_url,
                    sort_order=position + 1,
                )
            )
            await session.flush()
    await session.commit()


async def _categories(session: AsyncSession, branch_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(Category.name, Category.id).where(
            Category.branch_id == branch_id, Category.is_archived.is_(False)
        )
    )
    return [(name, cid) for name, cid in rows]


async def _existing_dishes(
    session: AsyncSession, branch_id: int
) -> dict[tuple[str, str], int]:
    """Пары «категория + название» -> id, для сопоставления строк файла."""
    rows = await session.execute(
        select(Category.name, Dish.name, Dish.id)
        .join(Dish, Dish.category_id == Category.id)
        .where(Category.branch_id == branch_id, Category.is_archived.is_(False))
    )
    return {(c.lower(), d.lower()): dish_id for c, d, dish_id in rows}
