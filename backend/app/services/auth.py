"""Вход владельца: пароли, сессии, защита от перебора."""

import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminSession, AdminUser

SESSION_TTL_DAYS = 30
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15

_hasher = PasswordHasher()


class LoginFailed(Exception):
    """Неверный логин или пароль. Намеренно не уточняем, что именно."""


class LoginLocked(Exception):
    def __init__(self, until: datetime):
        self.until = until


def hash_password(password: str) -> str:
    return _hasher.hash(password)


async def authenticate(
    session: AsyncSession, login: str, password: str
) -> AdminUser:
    """Проверить пару логин/пароль и вернуть пользователя.

    Считает неудачные попытки: после MAX_FAILED_ATTEMPTS подряд вход
    блокируется на LOCK_MINUTES, чтобы пароль нельзя было подобрать перебором.
    """
    user = await session.scalar(select(AdminUser).where(AdminUser.login == login))
    if user is None:
        # проверяем «пустой» хеш, чтобы ответ занимал столько же времени
        # и по задержке нельзя было понять, есть ли такой логин
        _dummy_verify()
        raise LoginFailed()

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        raise LoginLocked(user.locked_until)

    try:
        _hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        await session.commit()
        raise LoginFailed() from None

    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    user.failed_attempts = 0
    user.locked_until = None
    await session.commit()
    return user


async def change_password(
    session: AsyncSession, user: AdminUser, current: str, new: str
) -> None:
    """Смена пароля владельцем. LoginFailed — текущий пароль не подошёл.

    Все сессии пользователя гасятся: смена пароля обязана выкидывать чужие
    устройства, иначе она не спасает от того, у кого пароль утёк.
    """
    try:
        _hasher.verify(user.password_hash, current)
    except VerifyMismatchError:
        raise LoginFailed() from None

    user.password_hash = hash_password(new)
    await session.execute(
        delete(AdminSession).where(AdminSession.user_id == user.id)
    )
    await session.commit()


def _dummy_verify() -> None:
    try:
        _hasher.verify(_hasher.hash("dummy"), "wrong")
    except VerifyMismatchError:
        pass


async def create_session(session: AsyncSession, user: AdminUser) -> AdminSession:
    """Новая сессия. Заодно подчищаем просроченные."""
    await session.execute(
        delete(AdminSession).where(AdminSession.expires_at < datetime.now(UTC))
    )
    row = AdminSession(
        token=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=SESSION_TTL_DAYS),
    )
    session.add(row)
    await session.commit()
    return row


async def user_by_session(
    session: AsyncSession, token: str | None
) -> AdminUser | None:
    if not token:
        return None
    row = await session.scalar(
        select(AdminSession).where(
            AdminSession.token == token,
            AdminSession.expires_at > datetime.now(UTC),
        )
    )
    return await session.get(AdminUser, row.user_id) if row else None


async def drop_session(session: AsyncSession, token: str | None) -> None:
    if not token:
        return
    await session.execute(delete(AdminSession).where(AdminSession.token == token))
    await session.commit()
