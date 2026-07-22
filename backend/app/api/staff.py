"""Персонал заведения: приглашения в бота, роли, увольнение.

Раздел закрыт require_admin: по ссылке-приглашению человек получает доступ к
кнопкам кухни, поэтому раздавать их может только владелец.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_branch, require_admin
from app.bot.instance import get_bot_username
from app.core.db import get_session
from app.models import Branch, Staff
from app.schemas.staff import (
    StaffInviteIn,
    StaffInviteOut,
    StaffOut,
    StaffPatch,
)

router = APIRouter(prefix="/admin/staff", tags=["admin"])


def _deep_link(username: str | None, token: str | None) -> str | None:
    """Готовая ссылка t.me/<bot>?start=<token>. None — бот выключен или инвайт погашен."""
    return f"https://t.me/{username}?start={token}" if username and token else None


def _out(staff: Staff, username: str | None) -> StaffOut:
    return StaffOut(
        id=staff.id,
        full_name=staff.full_name,
        role=staff.role,
        is_active=staff.is_active,
        is_connected=staff.telegram_chat_id is not None,
        deep_link=_deep_link(username, staff.invite_token),
    )


async def _staff_or_404(
    session: AsyncSession, staff_id: int, branch: Branch
) -> Staff:
    staff = await session.get(Staff, staff_id)
    if staff is None or staff.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return staff


@router.get("", response_model=list[StaffOut])
async def list_staff(
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Все сотрудники, включая уволенных — их владелец должен видеть."""
    rows = (
        await session.scalars(
            select(Staff).where(Staff.branch_id == branch.id).order_by(Staff.id)
        )
    ).all()
    username = await get_bot_username()
    return [_out(s, username) for s in rows]


@router.post("", response_model=StaffInviteOut, status_code=201)
async def create_invite(
    body: StaffInviteIn,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Одноразовое приглашение сотрудника (повар/официант) в Telegram-бота."""
    token = secrets.token_urlsafe(16)
    staff = Staff(
        branch_id=branch.id,
        full_name=body.full_name,
        role=body.role,
        invite_token=token,
    )
    session.add(staff)
    await session.commit()

    username = await get_bot_username()
    return StaffInviteOut(
        staff_id=staff.id,
        invite_token=token,
        deep_link=_deep_link(username, token),
    )


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff(
    staff_id: int,
    body: StaffPatch,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Правка имени и роли, а также возврат уволенного (is_active = true)."""
    staff = await _staff_or_404(session, staff_id, branch)
    for field in ("full_name", "role", "is_active"):
        value = getattr(body, field)
        if value is not None:
            setattr(staff, field, value)
    await session.commit()
    return _out(staff, await get_bot_username())


@router.post("/{staff_id}/reinvite", response_model=StaffInviteOut)
async def reinvite(
    staff_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Новая ссылка: сотрудник сменил телефон или потерял старую.

    Прежняя привязка к Telegram сбрасывается — иначе заказы продолжали бы
    засчитываться аккаунту, которым человек уже не пользуется.
    """
    staff = await _staff_or_404(session, staff_id, branch)
    token = secrets.token_urlsafe(16)
    staff.invite_token = token
    staff.telegram_chat_id = None
    staff.is_active = True
    await session.commit()

    return StaffInviteOut(
        staff_id=staff.id,
        invite_token=token,
        deep_link=_deep_link(await get_bot_username(), token),
    )


@router.delete("/{staff_id}", status_code=204)
async def dismiss(
    staff_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Увольнение: строку не удаляем — на неё опирается прошлая статистика.

    telegram_chat_id намеренно остаётся: статистика ищет имя именно по нему, и
    без него прошлые смены человека превратились бы в голые «ID 12345».
    Доступ к кнопкам всё равно даёт членство в группе заведения, а не эта
    таблица, — уволенного нужно удалить из чата.
    """
    staff = await _staff_or_404(session, staff_id, branch)
    staff.is_active = False
    staff.invite_token = None
    await session.commit()
