"""Ведение меню владельцем: категории, блюда, цены, стоп-лист, порядок, фото."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import current_branch, require_admin
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Branch, Category, Dish
from app.services import menu_import
from app.services.photos import (
    PhotoBroken,
    PhotoTooBig,
    delete_dish_photo,
    save_dish_photo,
)
from app.schemas.menu_admin import (
    AdminCategoryOut,
    AdminDishOut,
    AdminMenuOut,
    CategoryIn,
    CategoryPatch,
    DishIn,
    DishPatch,
    ImportReportOut,
    ImportRowOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _dish_or_404(session: AsyncSession, dish_id: int) -> Dish:
    dish = await session.get(Dish, dish_id)
    if dish is None or dish.is_archived:
        raise HTTPException(status_code=404, detail="Блюдо не найдено")
    return dish


async def _category_or_404(session: AsyncSession, category_id: int) -> Category:
    category = await session.get(Category, category_id)
    if category is None or category.is_archived:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return category


def _category_out(
    category: Category, dishes: list[AdminDishOut] | None = None
) -> AdminCategoryOut:
    """Одна сборка ответа на все ручки категорий — чтобы поля не разъезжались."""
    return AdminCategoryOut(
        id=category.id,
        name=category.name,
        name_kk=category.name_kk,
        sort_order=category.sort_order,
        available_from=category.available_from,
        available_to=category.available_to,
        dishes=dishes or [],
    )


@router.get("/menu", response_model=AdminMenuOut)
async def admin_menu(
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Всё меню, включая блюда в стоп-листе — их владелец должен видеть."""
    categories = (
        await session.scalars(
            select(Category)
            .where(
                Category.branch_id == branch.id, Category.is_archived.is_(False)
            )
            .order_by(Category.sort_order, Category.id)
            .options(
                selectinload(Category.dishes.and_(Dish.is_archived.is_(False)))
            )
        )
    ).all()
    return AdminMenuOut(
        branch_name=branch.name,
        menu_disclaimer=branch.menu_disclaimer,
        categories=[
            _category_out(c, [AdminDishOut.model_validate(d) for d in c.dishes])
            for c in categories
        ],
    )


@router.post("/categories", response_model=AdminCategoryOut, status_code=201)
async def create_category(
    body: CategoryIn,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    last = await session.scalar(
        select(func.coalesce(func.max(Category.sort_order), 0)).where(
            Category.branch_id == branch.id
        )
    )
    category = Category(branch_id=branch.id, name=body.name, sort_order=last + 1)
    session.add(category)
    await session.commit()
    return _category_out(category)


@router.patch("/categories/{category_id}", response_model=AdminCategoryOut)
async def update_category(
    category_id: int,
    body: CategoryPatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Переименование и часы показа (бизнес-ланч, завтраки, ночное меню)."""
    category = await _category_or_404(session, category_id)
    if body.name is not None:
        category.name = body.name
    if body.name_kk is not None:
        category.name_kk = body.name_kk.strip() or None
    if body.clear_schedule:
        category.available_from = None
        category.available_to = None
    else:
        if body.available_from is not None:
            category.available_from = body.available_from
        if body.available_to is not None:
            category.available_to = body.available_to
    await session.commit()
    return _category_out(category)


@router.delete("/categories/{category_id}", status_code=204)
async def archive_category(
    category_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Убрать категорию вместе с её блюдами (архивирование, не удаление)."""
    category = await _category_or_404(session, category_id)
    category.is_archived = True
    dishes = (
        await session.scalars(select(Dish).where(Dish.category_id == category.id))
    ).all()
    for dish in dishes:
        dish.is_archived = True
    await session.commit()


@router.post("/categories/{category_id}/move", response_model=AdminCategoryOut)
async def move_category(
    category_id: int,
    direction: str,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Переставить категорию в меню. Меняемся местами с соседом."""
    if direction not in ("up", "down"):
        raise HTTPException(status_code=422, detail="direction: up | down")
    category = await _category_or_404(session, category_id)

    neighbours = (
        await session.scalars(
            select(Category)
            .where(
                Category.branch_id == branch.id, Category.is_archived.is_(False)
            )
            .order_by(Category.sort_order, Category.id)
        )
    ).all()
    index = next(i for i, c in enumerate(neighbours) if c.id == category.id)
    swap_with = index - 1 if direction == "up" else index + 1
    if 0 <= swap_with < len(neighbours):
        other = neighbours[swap_with]
        # порядок может быть с дырами и повторами — переприсваиваем подряд
        for position, item in enumerate(neighbours, start=1):
            item.sort_order = position
        category.sort_order, other.sort_order = other.sort_order, category.sort_order
        await session.commit()
    return _category_out(category)


@router.post("/dishes", response_model=AdminDishOut, status_code=201)
async def create_dish(
    body: DishIn,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _category_or_404(session, body.category_id)
    last = await session.scalar(
        select(func.coalesce(func.max(Dish.sort_order), 0)).where(
            Dish.category_id == body.category_id
        )
    )
    dish = Dish(
        category_id=body.category_id,
        name=body.name,
        name_kk=body.name_kk,
        description=body.description,
        description_kk=body.description_kk,
        price=body.price,
        cost_price=body.cost_price,
        image_url=body.image_url,
        is_veg=body.is_veg,
        is_spicy=body.is_spicy,
        is_hit=body.is_hit,
        is_chef=body.is_chef,
        allergens=body.allergens,
        sort_order=last + 1,
    )
    session.add(dish)
    await session.commit()
    return AdminDishOut.model_validate(dish)


@router.patch("/dishes/{dish_id}", response_model=AdminDishOut)
async def update_dish(
    dish_id: int,
    body: DishPatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Правка блюда. Цена меняется только вперёд: в заказах лежат снапшоты."""
    dish = await _dish_or_404(session, dish_id)
    if body.category_id is not None:
        await _category_or_404(session, body.category_id)
        dish.category_id = body.category_id
    # у переводов пустая строка означает «убрать», а None — «не присылали»
    for field in ("name_kk", "description_kk"):
        value = getattr(body, field)
        if value is not None:
            setattr(dish, field, value.strip() or None)

    for field in (
        "name",
        "price",
        "cost_price",
        "description",
        "image_url",
        "is_active",
        "is_veg",
        "is_spicy",
        "is_hit",
        "is_chef",
        "allergens",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(dish, field, value)
    await session.commit()
    return AdminDishOut.model_validate(dish)


@router.delete("/dishes/{dish_id}", status_code=204)
async def archive_dish(
    dish_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    dish = await _dish_or_404(session, dish_id)
    dish.is_archived = True
    await session.commit()


@router.get("/menu/import/template")
async def import_template(_actor: str = Depends(require_admin)):
    """Шаблон таблицы: владельцу проще заполнить готовый файл."""
    return Response(
        content=menu_import.TEMPLATE.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="menu-template.csv"'},
    )


@router.post("/menu/import", response_model=ImportReportOut)
async def import_menu(
    file: UploadFile = File(...),
    dry_run: bool = True,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Заливка меню таблицей.

    По умолчанию только разбирает файл и показывает, что произойдёт —
    массовая правка вслепую слишком легко ломает всё меню.
    """
    try:
        report = await menu_import.parse(session, branch.id, await file.read())
    except menu_import.ImportBroken as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    if not dry_run and report.rows:
        await menu_import.apply(session, branch.id, report)

    return ImportReportOut(
        applied=not dry_run and bool(report.rows),
        to_create=report.to_create,
        to_update=report.to_update,
        new_categories=report.new_categories,
        errors=report.errors,
        preview=[
            ImportRowOut(
                line=r.line,
                category=r.category,
                name=r.name,
                price=r.price,
                action=r.action,
            )
            for r in report.rows[:50]
        ],
    )


@router.post("/dishes/{dish_id}/photo", response_model=AdminDishOut)
async def upload_dish_photo(
    dish_id: int,
    file: UploadFile = File(...),
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Фото блюда с телефона: пережимаем в WebP и подставляем в меню."""
    dish = await _dish_or_404(session, dish_id)
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Нужен файл изображения")

    try:
        url = save_dish_photo(Path(settings.media_root), dish.id, await file.read())
    except PhotoTooBig:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ") from None
    except PhotoBroken:
        raise HTTPException(status_code=422, detail="Не удалось прочитать фото") from None

    # метка времени в адресе — иначе браузер покажет старое фото из кэша
    dish.image_url = f"{url}?v={int(datetime.now(UTC).timestamp())}"
    await session.commit()
    return AdminDishOut.model_validate(dish)


@router.delete("/dishes/{dish_id}/photo", response_model=AdminDishOut)
async def delete_photo(
    dish_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    dish = await _dish_or_404(session, dish_id)
    delete_dish_photo(Path(settings.media_root), dish.id)
    dish.image_url = None
    await session.commit()
    return AdminDishOut.model_validate(dish)


@router.post("/dishes/{dish_id}/move", response_model=AdminDishOut)
async def move_dish(
    dish_id: int,
    direction: str,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Переставить блюдо в категории. Меняемся местами с соседом."""
    if direction not in ("up", "down"):
        raise HTTPException(status_code=422, detail="direction: up | down")
    dish = await _dish_or_404(session, dish_id)

    neighbours = (
        await session.scalars(
            select(Dish)
            .where(
                Dish.category_id == dish.category_id, Dish.is_archived.is_(False)
            )
            .order_by(Dish.sort_order, Dish.id)
        )
    ).all()
    index = next(i for i, d in enumerate(neighbours) if d.id == dish.id)
    swap_with = index - 1 if direction == "up" else index + 1
    if 0 <= swap_with < len(neighbours):
        other = neighbours[swap_with]
        # порядок может быть с дырами и повторами — переприсваиваем подряд
        for position, item in enumerate(neighbours, start=1):
            item.sort_order = position
        dish.sort_order, other.sort_order = other.sort_order, dish.sort_order
        await session.commit()
    return AdminDishOut.model_validate(dish)
