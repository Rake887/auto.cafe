import logging

from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from app.bot.instance import bot, dp
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Приём апдейтов от Telegram (режим webhook, не polling)."""
    settings = get_settings()
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot is not configured")
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Bad secret token")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    try:
        await dp.feed_update(bot, update)
    except Exception:
        # Telegram повторяет апдейт, на который получил не-200, поэтому
        # ошибку хендлера логируем, но подтверждаем приём.
        logger.exception("Ошибка обработки апдейта %s", update.update_id)
    return {"ok": True}
