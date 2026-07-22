"""Служебные ручки для показа демо: где сейчас лежит меню и QR на него."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Point
from app.services.qr import make_qr_svg
from app.services.tunnel import get_public_base, site_root

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoLink(BaseModel):
    """Куда вести гостя прямо сейчас."""

    # None, если туннель не поднят — тогда показываем только локальный адрес
    public_url: str | None
    menu_url: str | None
    point_label: str | None
    token: str | None


async def _demo_point(session: AsyncSession, settings: Settings) -> Point | None:
    """Стол с закреплённым демо-токеном, иначе просто первый по счёту."""
    if settings.demo_token:
        point = await session.scalar(
            select(Point).where(Point.token == settings.demo_token)
        )
        if point is not None:
            return point
    return await session.scalar(select(Point).order_by(Point.id).limit(1))


@router.get("/link", response_model=DemoLink)
async def demo_link(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Публичная ссылка на демо-меню — без чтения логов туннеля."""
    point = await _demo_point(session, settings)
    base = await get_public_base(settings)
    root = site_root(base, settings) if base else None
    return DemoLink(
        public_url=root,
        menu_url=f"{root}/m/{point.token}" if root and point else None,
        point_label=point.label if point else None,
        token=point.token if point else None,
    )


@router.get("/qr.svg", response_class=Response)
async def demo_qr(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """QR-код на демо-меню: навёл телефон — открыл. Тот же, что клеят на стол."""
    point = await _demo_point(session, settings)
    base = await get_public_base(settings)
    root = site_root(base, settings) if base else None
    target = f"{root}/m/{point.token}" if root and point else "about:blank"

    return Response(
        content=make_qr_svg(target),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )
