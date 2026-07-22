"""Вход и выход владельца."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, require_admin, require_admin_user
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import AdminUser
from app.services.auth import (
    SESSION_TTL_DAYS,
    LoginFailed,
    LoginLocked,
    authenticate,
    change_password,
    create_session,
    drop_session,
    hash_password,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    full_name: str


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        # на проде сайт под HTTPS — не отдаём cookie по открытому каналу
        secure=settings.cookie_secure,
        path="/",
    )


@router.post("/login", response_model=MeOut)
async def login(
    body: LoginIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Вход по логину и паролю. Возвращает cookie с токеном сессии."""
    try:
        user = await authenticate(session, body.login, body.password)
    except LoginLocked as e:
        raise HTTPException(
            status_code=429,
            detail=f"Слишком много попыток. Попробуйте после {e.until:%H:%M}",
        ) from None
    except LoginFailed:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль") from None

    row = await create_session(session, user)
    _set_session_cookie(response, row.token, settings)
    return MeOut(full_name=user.full_name)


class SetupIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=255)


class SetupStateOut(BaseModel):
    # true — владельца ещё нет, форма первичной настройки доступна
    needs_setup: bool


async def _no_admins(session: AsyncSession) -> bool:
    return (
        await session.scalar(select(func.count()).select_from(AdminUser))
    ) == 0


@router.get("/setup", response_model=SetupStateOut)
async def setup_state(session: AsyncSession = Depends(get_session)):
    """Нужна ли первичная настройка. Страница входа спрашивает это сама."""
    return SetupStateOut(needs_setup=await _no_admins(session))


@router.post("/setup", response_model=MeOut, status_code=201)
async def setup(
    body: SetupIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Создать владельца на пустой базе и сразу впустить его в кабинет.

    Ручка живёт ровно до появления первого администратора: дальше отдаёт 404,
    иначе любой желающий заводил бы себе доступ. Установщику это экономит
    заход по SSH — заведение подключается целиком из браузера.
    """
    if not await _no_admins(session):
        raise HTTPException(status_code=404, detail="Not Found")

    user = AdminUser(
        login=body.login,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # кто-то успел создать владельца между проверкой и вставкой
        await session.rollback()
        raise HTTPException(status_code=409, detail="Владелец уже создан") from None

    row = await create_session(session, user)
    _set_session_cookie(response, row.token, settings)
    return MeOut(full_name=user.full_name)


@router.post("/password", response_model=MeOut)
async def update_password(
    body: PasswordChangeIn,
    response: Response,
    user: AdminUser = Depends(require_admin_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Смена собственного пароля из кабинета.

    Старые сессии гасятся все разом, поэтому взамен сразу выдаём новую —
    иначе владелец выкинул бы сам себя на страницу входа.
    """
    try:
        await change_password(session, user, body.current_password, body.new_password)
    except LoginFailed:
        raise HTTPException(status_code=401, detail="Текущий пароль неверен") from None

    row = await create_session(session, user)
    _set_session_cookie(response, row.token, settings)
    return MeOut(full_name=user.full_name)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    qrmenu_admin: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    await drop_session(session, qrmenu_admin)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
async def me(actor: str = Depends(require_admin)):
    """Кто вошёл. Фронтенд по этой ручке решает, пускать ли на страницы."""
    return MeOut(full_name=actor)
