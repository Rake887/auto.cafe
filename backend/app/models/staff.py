import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StaffRole(str, enum.Enum):
    cook = "cook"
    waiter = "waiter"


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branch.id"))
    # null, пока сотрудник не активировал инвайт через /start в боте
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole, name="staff_role"))
    full_name: Mapped[str] = mapped_column(String(255))
    # одноразовый токен приглашения; обнуляется после регистрации
    invite_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Увольнение — снятие флага, а не удаление строки: на статистику прошлых
    # смен ссылается telegram_chat_id, и без записи в ней остались бы голые id
    is_active: Mapped[bool] = mapped_column(default=True)
