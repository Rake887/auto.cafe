"""Синглтоны aiogram: Bot и Dispatcher.

Бот может быть выключен (BOT_TOKEN пуст) — тогда bot is None, а все
отправки уведомлений тихо пропускаются. Это позволяет гонять API-часть
без настройки Telegram.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import get_settings

_settings = get_settings()

bot: Bot | None = (
    Bot(
        token=_settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if _settings.bot_enabled
    else None
)

dp = Dispatcher()

_bot_username: str | None = None


async def get_bot_username() -> str | None:
    """Юзернейм бота (кэшируется) — для сборки диплинк-ссылок инвайтов."""
    global _bot_username
    if bot is None:
        return None
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return _bot_username
