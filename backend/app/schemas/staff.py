from pydantic import BaseModel, Field

from app.models import StaffRole


class StaffInviteIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: StaffRole


class StaffInviteOut(BaseModel):
    staff_id: int
    invite_token: str
    # готовая диплинк-ссылка t.me/<bot>?start=<token>; null, если бот не настроен
    deep_link: str | None


class StaffOut(BaseModel):
    """Сотрудник глазами владельца."""

    id: int
    full_name: str
    role: StaffRole
    is_active: bool
    # прошёл ли /start в боте: пока нет, кнопки кухни ему не приходят
    is_connected: bool
    # непогашенное приглашение; null — сотрудник уже зарегистрирован
    deep_link: str | None


class StaffPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: StaffRole | None = None
    # false — уволен, true — вернули на работу
    is_active: bool | None = None
