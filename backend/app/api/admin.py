"""Статистика заведения и данные для печати наклеек.

Доступ — через require_admin: сессия владельца или машинный ключ.
"""

import secrets
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_branch, require_admin
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Branch, Point, Zone
from app.schemas.admin import (
    AdminStats,
    PointIn,
    PointOut,
    PointPatch,
    PointsResponse,
    ZoneIn,
    ZoneOut,
    ZonePatch,
)
from app.schemas.menu_admin import (
    BranchOut,
    BranchPatch,
    PlaceLinkIn,
    PlaceLinkOut,
)
from app.services.orders import client_ip, is_public_ip
from app.services.place_link import (
    expand_short_link,
    parse_place_link,
    verify_url,
)
from app.services.qr import make_qr_svg
from app.services.stats import PERIODS, collect_stats
from app.services.tunnel import get_public_base, site_root

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    period: str = Query(default="day"),
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Выручка, заказы, топ блюд и работа персонала за период."""
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period: {', '.join(PERIODS)}")

    branch_id = await session.scalar(
        select(Branch.id)
        .where(Branch.organization_id == settings.demo_organization_id)
        .order_by(Branch.id)
        .limit(1)
    )
    if branch_id is None:
        raise HTTPException(status_code=409, detail="Нет филиала — прогоните сидинг")

    return await collect_stats(session, branch_id, period)


@router.get("/my-ip")
async def my_ip(request: Request, _actor: str = Depends(require_admin)):
    """IP, с которого пришёл этот запрос.

    Владелец нажимает кнопку, стоя в своём зале на его Wi-Fi, — и заведение
    запоминает свой публичный адрес, не выясняя его через сторонние сервисы.
    Запрос обязан идти из браузера: со стороны SSR это был бы адрес контейнера.
    """
    found = client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    return {
        "ip": found,
        # внутренний адрес сохранять нельзя — он одинаков у всех гостей
        "usable": bool(found and is_public_ip(found)),
    }


@router.post("/branch/place-link", response_model=PlaceLinkOut)
async def geo_from_link(
    body: PlaceLinkIn,
    _actor: str = Depends(require_admin),
):
    """Координаты заведения из ссылки на карту.

    Точка берётся из карточки заведения, а не с устройства владельца: он почти
    наверняка настраивает кабинет из дома, и тогда в базу легли бы координаты
    его квартиры.
    """
    url = await expand_short_link(body.url.strip())
    found = parse_place_link(url)
    if found is None:
        raise HTTPException(
            status_code=422,
            detail="В ссылке нет координат. Откройте заведение в 2ГИС, "
            "Яндекс Картах или Google Maps и скопируйте адрес из строки "
            "браузера — короткая ссылка «Поделиться» тоже подойдёт.",
        )

    lat, lon, source = found
    return PlaceLinkOut(
        lat=lat, lon=lon, source=source, verify_url=verify_url(lat, lon)
    )


@router.get("/branch", response_model=BranchOut)
async def read_branch(
    _actor: str = Depends(require_admin),
    branch: Branch = Depends(current_branch),
):
    return BranchOut.model_validate(branch)


@router.patch("/branch", response_model=BranchOut)
async def update_branch(
    body: BranchPatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Название заведения, предупреждение об аллергенах и ссылка на отзывы.

    Пустая строка здесь значит «убрать», поэтому она не равна None: None —
    «поле не прислали, не трогать».
    """
    if body.name is not None:
        branch.name = body.name
    if body.menu_disclaimer is not None:
        branch.menu_disclaimer = body.menu_disclaimer.strip() or None
    if body.review_url is not None:
        branch.review_url = body.review_url.strip() or None
    if body.accepting_orders is not None:
        branch.accepting_orders = body.accepting_orders

    if body.clear_hours:
        branch.opens_at = None
        branch.closes_at = None
    else:
        if body.opens_at is not None:
            branch.opens_at = body.opens_at
        if body.closes_at is not None:
            branch.closes_at = body.closes_at

    if body.trusted_ip is not None:
        candidate = body.trusted_ip.strip()
        if candidate and not is_public_ip(candidate):
            raise HTTPException(
                status_code=422,
                detail="Это внутренний адрес, а не публичный IP заведения. "
                "Нажмите «Мой IP», открыв кабинет по настоящему домену с "
                "Wi-Fi заведения — через туннель адрес будет техническим и "
                "признак сработал бы на всех гостей подряд.",
            )
        branch.trusted_ip = candidate or None

    if body.clear_geo:
        branch.lat = branch.lon = branch.geo_radius_m = None
    else:
        if body.lat is not None:
            branch.lat = Decimal(str(body.lat))
        if body.lon is not None:
            branch.lon = Decimal(str(body.lon))
        if body.geo_radius_m is not None:
            branch.geo_radius_m = body.geo_radius_m

    await session.commit()
    return BranchOut.model_validate(branch)


async def _point_or_404(session: AsyncSession, point_id: int, branch: Branch) -> Point:
    point = await session.get(Point, point_id)
    if point is None or point.branch_id != branch.id or point.is_archived:
        raise HTTPException(status_code=404, detail="Стол не найден")
    return point


async def _zone_or_404(session: AsyncSession, zone_id: int, branch: Branch) -> Zone:
    zone = await session.get(Zone, zone_id)
    if zone is None or zone.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Зона не найдена")
    return zone


async def _zones(session: AsyncSession, branch: Branch) -> list[Zone]:
    return list(
        (
            await session.scalars(
                select(Zone)
                .where(Zone.branch_id == branch.id)
                .order_by(Zone.sort_order, Zone.id)
            )
        ).all()
    )


def _point_out(point: Point, zone_name: str, root: str | None) -> PointOut:
    return PointOut(
        id=point.id,
        label=point.label,
        token=point.token,
        zone_id=point.zone_id,
        zone_name=zone_name,
        menu_url=f"{root}/m/{point.token}" if root else None,
    )


@router.get("/zones", response_model=list[ZoneOut])
async def admin_zones(
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    return [ZoneOut.model_validate(z) for z in await _zones(session, branch)]


@router.post("/zones", response_model=ZoneOut, status_code=201)
async def create_zone(
    body: ZoneIn,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Новая зона. Нумерация заказов в ней начинается со своей единицы."""
    last = await session.scalar(
        select(func.coalesce(func.max(Zone.sort_order), 0)).where(
            Zone.branch_id == branch.id
        )
    )
    zone = Zone(branch_id=branch.id, name=body.name, sort_order=last + 1)
    session.add(zone)
    await session.commit()
    return ZoneOut.model_validate(zone)


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
async def update_zone(
    zone_id: int,
    body: ZonePatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    zone = await _zone_or_404(session, zone_id, branch)
    if body.name is not None:
        zone.name = body.name
    await session.commit()
    return ZoneOut.model_validate(zone)


@router.delete("/zones/{zone_id}", status_code=204)
async def delete_zone(
    zone_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Удалить зону можно только пустую: столам нужно куда-то встать.

    Последнюю зону тоже не удаляем — иначе новый стол создать было бы негде.
    """
    zone = await _zone_or_404(session, zone_id, branch)
    occupied = await session.scalar(
        select(func.count())
        .select_from(Point)
        .where(Point.zone_id == zone.id, Point.is_archived.is_(False))
    )
    if occupied:
        raise HTTPException(
            status_code=409,
            detail="В зоне есть столы — сначала перенесите их в другую зону",
        )
    if len(await _zones(session, branch)) <= 1:
        raise HTTPException(
            status_code=409, detail="Это последняя зона, её нельзя убрать"
        )
    await session.delete(zone)
    await session.commit()


@router.get("/points", response_model=PointsResponse)
async def admin_points(
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    branch: Branch = Depends(current_branch),
):
    """Столы с их публичными ссылками — для страницы печати наклеек."""
    base = await get_public_base(settings)
    root = site_root(base, settings) if base else None
    zones = await _zones(session, branch)
    names = {z.id: z.name for z in zones}
    points = (
        await session.scalars(
            select(Point)
            .where(Point.branch_id == branch.id, Point.is_archived.is_(False))
            .order_by(Point.zone_id, Point.id)
        )
    ).all()
    return PointsResponse(
        site_url=root,
        zones=[ZoneOut.model_validate(z) for z in zones],
        points=[_point_out(p, names.get(p.zone_id, ""), root) for p in points],
    )


async def _root(settings: Settings) -> str | None:
    base = await get_public_base(settings)
    return site_root(base, settings) if base else None


@router.post("/points", response_model=PointOut, status_code=201)
async def create_point(
    body: PointIn,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    branch: Branch = Depends(current_branch),
):
    """Новый стол. Токен генерируем здесь — гостю он попадёт только в QR."""
    zones = await _zones(session, branch)
    if body.zone_id is not None:
        zone = await _zone_or_404(session, body.zone_id, branch)
    elif zones:
        zone = zones[0]
    else:
        raise HTTPException(status_code=409, detail="Сначала создайте зону")

    point = Point(
        branch_id=branch.id,
        zone_id=zone.id,
        label=body.label,
        token=secrets.token_urlsafe(12),
    )
    session.add(point)
    await session.commit()
    return _point_out(point, zone.name, await _root(settings))


@router.patch("/points/{point_id}", response_model=PointOut)
async def update_point(
    point_id: int,
    body: PointPatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    branch: Branch = Depends(current_branch),
):
    point = await _point_or_404(session, point_id, branch)
    if body.label is not None:
        point.label = body.label
    zone = await _zone_or_404(session, body.zone_id or point.zone_id, branch)
    point.zone_id = zone.id
    await session.commit()
    return _point_out(point, zone.name, await _root(settings))


@router.post("/points/{point_id}/rotate", response_model=PointOut)
async def rotate_point_token(
    point_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    branch: Branch = Depends(current_branch),
):
    """Перевыпуск токена: наклейку сфотографировали и заказывают из дома.

    Старая ссылка перестаёт работать сразу, поэтому наклейку надо перепечатать.
    """
    point = await _point_or_404(session, point_id, branch)
    point.token = secrets.token_urlsafe(12)
    zone = await _zone_or_404(session, point.zone_id, branch)
    await session.commit()
    return _point_out(point, zone.name, await _root(settings))


@router.delete("/points/{point_id}", status_code=204)
async def archive_point(
    point_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Убрать стол. Архивирование, а не удаление: на него ссылаются заказы."""
    point = await _point_or_404(session, point_id, branch)
    point.is_archived = True
    await session.commit()


@router.get("/qr.svg", response_class=Response)
async def admin_qr(
    point: str,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """QR конкретного стола — то, что клеится на этот стол."""
    base = await get_public_base(settings)
    root = site_root(base, settings) if base else None
    if root is None:
        raise HTTPException(
            status_code=409, detail="Публичный адрес неизвестен — поднимите туннель"
        )

    exists = await session.scalar(
        select(Point.id).where(Point.token == point, Point.is_archived.is_(False))
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Стол не найден")

    return Response(
        content=make_qr_svg(f"{root}/m/{point}"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )
