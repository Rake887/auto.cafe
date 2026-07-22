"""Публичный адрес приложения: из настроек или у агента туннеля.

Бесплатный домен cloudflared меняется при каждом запуске, поэтому спрашиваем
его у самого агента — так ни в конфиге, ни в голове держать нечего.
"""

import logging

import aiohttp

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def get_public_base(settings: Settings) -> str | None:
    """Внешний адрес API, например https://xxx.trycloudflare.com/api.

    None — адрес неизвестен (туннель не поднят и WEBHOOK_URL пуст).
    """
    if settings.webhook_url:
        return settings.webhook_url.rstrip("/")
    if not settings.tunnel_metrics_url:
        return None
    url = settings.tunnel_metrics_url.rstrip("/") + "/quicktunnel"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                # cloudflared отдаёт JSON, но с заголовком text/plain
                hostname = (await resp.json(content_type=None))["hostname"]
    except Exception:
        logger.warning("Не удалось спросить адрес у туннеля (%s)", url)
        return None
    return f"https://{hostname}{settings.webhook_path_prefix}"


def site_root(public_base: str, settings: Settings) -> str:
    """Адрес сайта для гостя: тот же домен без префикса API."""
    prefix = settings.webhook_path_prefix
    return public_base[: -len(prefix)] if prefix and public_base.endswith(prefix) else public_base
