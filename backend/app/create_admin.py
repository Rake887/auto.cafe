"""Создание владельца: python -m app.create_admin

Пароль спрашивается интерактивно и не принимается аргументом — иначе он осел бы
в истории команд и в логах оболочки.
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.db import async_session_factory, engine
from app.models import AdminUser
from app.services.auth import hash_password

MIN_PASSWORD_LEN = 8


async def create_admin() -> int:
    login = input("Логин: ").strip()
    if not login:
        print("Логин не может быть пустым.")
        return 1

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(AdminUser).where(AdminUser.login == login)
        )
        if existing is not None:
            answer = input(
                f"Пользователь «{login}» уже есть. Сменить пароль? [y/N] "
            ).strip().lower()
            if answer != "y":
                return 1

        password = getpass.getpass("Пароль: ")
        if len(password) < MIN_PASSWORD_LEN:
            print(f"Пароль короче {MIN_PASSWORD_LEN} символов.")
            return 1
        if password != getpass.getpass("Пароль ещё раз: "):
            print("Пароли не совпадают.")
            return 1

        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.failed_attempts = 0
            existing.locked_until = None
            await session.commit()
            print(f"Пароль пользователя «{login}» обновлён.")
            return 0

        full_name = input("Имя (как показывать в админке): ").strip() or login
        session.add(
            AdminUser(
                login=login,
                password_hash=hash_password(password),
                full_name=full_name,
            )
        )
        await session.commit()
        print(f"Пользователь «{login}» создан. Вход — на /admin/login")
        return 0


async def _main() -> int:
    try:
        return await create_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
