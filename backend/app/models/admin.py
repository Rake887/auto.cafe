from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AdminUser(Base):
    """Владелец заведения — тот, кто ведёт меню и смотрит статистику."""

    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # неудачные попытки входа подряд и время последней — защита от перебора,
    # в БД, а не в памяти, чтобы счётчик переживал перезапуск
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list["AdminSession"]] = relationship(back_populates="user")


class AdminSession(Base):
    """Серверная сессия: в cookie уходит только случайный токен.

    Хранение на сервере даёт настоящий выход и возможность отозвать доступ,
    чего не умеет самоподписанный токен вроде JWT.
    """

    __tablename__ = "admin_session"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[AdminUser] = relationship(back_populates="sessions")
