from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.menu import MenuResponse
from app.services.menu import get_menu_by_token

router = APIRouter(tags=["menu"])


@router.get("/m/{token}", response_model=MenuResponse)
async def get_menu(
    token: str,
    lang: str = "ru",
    session: AsyncSession = Depends(get_session),
):
    """Меню филиала по QR-токену стола: филиал + категории + блюда одним запросом.

    lang уходит в адрес, а не в заголовок: у SSR-кэша разные ключи на язык,
    и казахская версия не подменит русскую.
    """
    menu = await get_menu_by_token(session, token, lang)
    if menu is None:
        raise HTTPException(status_code=404, detail="Стол с таким QR-кодом не найден")
    return menu
