"""Кто нажал кнопку в боте: сопоставление telegram-id с сотрудником."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Staff, StaffRole


async def staff_by_telegram(
    session: AsyncSession,
    telegram_ids: list[int],
    branch_id: int,
    expected_role: StaffRole | None = None,
) -> dict[int, Staff]:
    """Сотрудники по их telegram-id.

    Один аккаунт может быть заведён дважды (например, и поваром, и официантом),
    поэтому при совпадении предпочитаем запись с ожидаемой ролью.
    """
    if not telegram_ids:
        return {}
    rows = (
        await session.scalars(
            select(Staff)
            .where(
                Staff.branch_id == branch_id,
                Staff.telegram_chat_id.in_(telegram_ids),
            )
            .order_by(Staff.id)
        )
    ).all()

    by_chat: dict[int, Staff] = {}
    for staff in rows:
        chat_id = staff.telegram_chat_id
        current = by_chat.get(chat_id)
        if current is None or (
            expected_role is not None
            and current.role != expected_role
            and staff.role == expected_role
        ):
            by_chat[chat_id] = staff
    return by_chat


async def staff_name(
    session: AsyncSession,
    telegram_id: int | None,
    branch_id: int,
    expected_role: StaffRole | None = None,
) -> str | None:
    """Имя сотрудника для показа гостю. None — не нашли, лучше промолчать."""
    if telegram_id is None:
        return None
    found = await staff_by_telegram(session, [telegram_id], branch_id, expected_role)
    staff = found.get(telegram_id)
    return staff.full_name if staff else None
