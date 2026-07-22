from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаются из окружения / .env."""

    database_url: str = "postgresql+asyncpg://qrmenu:qrmenu@localhost:5432/qrmenu"

    bot_token: str = ""
    # Пусто — адрес вебхука спросим у туннеля (см. tunnel_metrics_url)
    webhook_url: str = ""
    # Служебный порт cloudflared, где он сообщает выданный ему адрес
    tunnel_metrics_url: str = ""
    # Префикс, под которым API живёт за прокси: туннель смотрит на прокси,
    # а тот отдаёт бэкенду всё, что начинается с /api
    webhook_path_prefix: str = "/api"
    webhook_secret: str = "change-me"
    group_chat_id: int = 0

    # Получать обновления опросом вместо вебхука. Нужно для локальной работы:
    # Telegram не резолвит имена бесплатных туннелей (*.trycloudflare.com),
    # вебхук туда не встаёт, и кнопки в чате молча не работают. На проде с
    # настоящим доменом оставляем вебхук — он дешевле и не держит соединение.
    bot_polling: bool = False

    # Через сколько минут напомнить в чат о заказе, который никто не принял.
    # 0 — напоминания выключены.
    order_reminder_minutes: int = 5
    # Заказы старше этого возраста уже неактуальны (гость ушёл, смена
    # закончилась) — про них не напоминаем, иначе после простоя бот вываливает
    # в чат пачку сообщений о вчерашних заказах.
    order_reminder_max_minutes: int = 60

    # Через сколько секунд вызов официанта, который никто не принял, считается
    # просроченным и дёргает чат повторно. 0 — эскалация выключена.
    service_call_sla_seconds: int = 90

    # Куда складывать фотографии блюд (том в docker-compose)
    media_root: str = "/srv/media"

    # Часовой пояс заведения. created_at хранится в UTC, и без пересчёта
    # «час пик» в статистике съедет на пять часов.
    display_timezone: str = "Asia/Almaty"

    demo_organization_id: int = 1
    # Если задан, сидинг выдаст этот токен первому столу — чтобы демо-ссылку
    # не приходилось переписывать после каждого пересоздания базы.
    # Для реального заведения оставить пустым: токены должны быть случайными.
    demo_token: str = ""
    # Машинный ключ к админ-API (для curl и скриптов). Люди входят по паролю.
    admin_token: str = ""
    # На проде сайт под HTTPS — cookie сессии не должна уходить по http
    cookie_secure: bool = False

    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def bot_enabled(self) -> bool:
        return bool(self.bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
