"""Общие зависимости API."""

import secrets

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import AdminUser, Branch
from app.services.auth import user_by_session

SESSION_COOKIE = "qrmenu_admin"


async def require_admin(
    qrmenu_admin: str | None = Cookie(default=None),
    token: str | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> str:
    """Доступ к админке: сессия из cookie или машинный ключ в ?token=.

    Ключ оставлен для скриптов и curl; люди ходят по сессии. Ответ на отказ —
    404, чтобы по коду ответа нельзя было понять, что раздел существует.
    """
    user = await user_by_session(session, qrmenu_admin)
    if user is not None:
        return user.full_name

    if (
        token
        and settings.admin_token
        and secrets.compare_digest(token, settings.admin_token)
    ):
        return "скрипт"

    raise HTTPException(status_code=404, detail="Not Found")


async def require_admin_user(
    qrmenu_admin: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    """Сам вошедший человек, а не только его имя.

    Машинный ключ здесь не принимается: он не привязан к учётной записи, а
    операции вроде смены пароля должны знать, чей пароль меняют.
    """
    user = await user_by_session(session, qrmenu_admin)
    if user is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return user


async def current_branch(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Branch:
    """Филиал заведения. В MVP он один — берём первый по порядку."""
    branch = await session.scalar(
        select(Branch)
        .where(Branch.organization_id == settings.demo_organization_id)
        .order_by(Branch.id)
        .limit(1)
    )
    if branch is None:
        raise HTTPException(status_code=409, detail="Нет филиала — прогоните сидинг")
    return branch
