import asyncio
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin,
    auth,
    calls,
    demo,
    menu,
    menu_admin,
    orders,
    orders_admin,
    pulse,
    reviews,
    staff,
    telegram,
)
from app.bot.handlers import router as bot_router
from app.bot.instance import bot, dp
from app.core.config import get_settings
from app.services.reminders import reminder_watcher
from app.services.tunnel import get_public_base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp.include_router(bot_router)


# Как часто проверять, не сменился ли внешний адрес
WEBHOOK_CHECK_INTERVAL_SEC = 30

# То, что мы реально обрабатываем: команды, нажатия кнопок и добавление
# бота в чат заведения. Список общий для обоих режимов получения обновлений.
ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member"]


async def polling_worker() -> None:
    """Локальная разработка: бот сам ходит к Telegram за обновлениями.

    Вебхуку нужен публичный адрес, который Telegram сумеет разрезолвить, а
    имена бесплатных быстрых туннелей (*.trycloudflare.com) он не резолвит
    вовсе. Со стороны это выглядит как «кнопки тормозят»: нажатие не доходит,
    бот не отвечает, и крутилка в чате висит до таймаута. Опрос от внешнего
    адреса не зависит и переживает любые перезапуски туннеля.
    """
    # Telegram не разрешает вебхук и опрос одновременно: пока адрес
    # зарегистрирован, getUpdates отвечает 409
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот работает опросом (BOT_POLLING=1), вебхук не нужен")
    # handle_signals=False обязателен: иначе aiogram перехватит сигналы
    # у uvicorn и контейнер перестанет корректно останавливаться
    await dp.start_polling(
        bot, allowed_updates=ALLOWED_UPDATES, handle_signals=False
    )


async def webhook_watcher() -> None:
    """Держит вебхук нацеленным на текущий адрес приложения.

    Бесплатный домен туннеля меняется при каждом его перезапуске, а на старте
    туннель может быть ещё не готов. Поэтому адрес не берётся один раз, а
    перепроверяется: изменился — перерегистрируем, и кнопки в чате оживают
    сами, без правки .env и рестарта.
    """
    settings = get_settings()
    registered: str | None = None
    while True:
        base = await get_public_base(settings)
        if base and base != registered:
            url = base + "/telegram/webhook"
            try:
                await bot.set_webhook(
                    url,
                    secret_token=settings.webhook_secret,
                    drop_pending_updates=True,
                    allowed_updates=ALLOWED_UPDATES,
                )
            except Exception:
                logger.exception("Не удалось зарегистрировать вебхук на %s", url)
            else:
                logger.info("Telegram webhook set to %s", url)
                registered = base
        elif base is None and registered is None:
            logger.warning(
                "Внешний адрес неизвестен (WEBHOOK_URL пуст и туннель не "
                "отвечает) — вебхук пока не установлен"
            )
        await asyncio.sleep(WEBHOOK_CHECK_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task[None]] = []
    if bot is None:
        logger.warning("BOT_TOKEN не задан — Telegram-уведомления выключены")
    else:
        # опрос — для локальной разработки, вебхук — для боевого домена
        if get_settings().bot_polling:
            tasks.append(asyncio.create_task(polling_worker()))
        else:
            tasks.append(asyncio.create_task(webhook_watcher()))
        tasks.append(asyncio.create_task(reminder_watcher()))
    yield
    for task in tasks:
        task.cancel()
    if bot is not None:
        await bot.session.close()


app = FastAPI(
    title="QR-Menu MVP API",
    description="Бэкенд демо QR-меню: гостевое меню, заказы, Telegram-бот кухни",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Фотографии блюд: том с диска отдаётся как /media, снаружи это /api/media/...
# В базовом образе нет записи для webp — без неё файлы уходят как
# application/octet-stream, и браузер отказывается их кэшировать как картинки.
mimetypes.add_type("image/webp", ".webp")
media_root = Path(settings.media_root)
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_root), name="media")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(menu_admin.router)
app.include_router(calls.router)
app.include_router(demo.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(orders_admin.router)
app.include_router(pulse.router)
app.include_router(reviews.router)
app.include_router(reviews.admin_router)
app.include_router(staff.router)
app.include_router(telegram.router)


@app.get("/health", tags=["service"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
