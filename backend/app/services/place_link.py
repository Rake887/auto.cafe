"""Координаты заведения из ссылки на карту.

Владелец обычно настраивает кабинет вечером из дома, поэтому брать точку с
устройства нельзя: в базу лягут координаты его квартиры, и проверка начнёт
врать в обе стороны — гости в зале станут «вне зала», а сам владелец дома
«в зале». Ссылка на карточку заведения от места настройки не зависит.

Ключевая тонкость — порядок чисел. У 2ГИС и Яндекса сначала долгота, у Google
сначала широта. Перепутать легко, а поймать трудно: для Тараза (42.9, 71.37)
перестановка даёт широту 71.37 — это Заполярье, но формально валидное число,
и никакой ошибки не возникнет. Поэтому порядок задаётся отдельно для каждого
сервиса, а результат в любом случае показывается владельцу на проверку.
"""

import re
from urllib.parse import unquote

import aiohttp

# Дробная часть обязательна: без неё выражения цепляют номера домов,
# уровни зума и куски идентификаторов
NUM = r"(-?\d+\.\d+)"

# (выражение, широта_первая) для каждого сервиса
_PATTERNS: dict[str, list[tuple[re.Pattern[str], bool]]] = {
    "2ГИС": [
        (re.compile(rf"/geo/\d+/{NUM},{NUM}"), False),
        (re.compile(rf"/center/{NUM},{NUM}"), False),
        (re.compile(rf"[?&]m={NUM},{NUM}"), False),
    ],
    "Яндекс Карты": [
        (re.compile(rf"[?&]ll={NUM},{NUM}"), False),
        (re.compile(rf"[?&]pt={NUM},{NUM}"), False),
    ],
    "Google Maps": [
        (re.compile(rf"@{NUM},{NUM}"), True),
        (re.compile(rf"[?&]q={NUM},{NUM}"), True),
    ],
}

_HOSTS = {
    "2gis.": "2ГИС",
    "yandex.": "Яндекс Карты",
    "google.": "Google Maps",
    "goo.gl": "Google Maps",
}

# Короткие ссылки координат не содержат — именно их даёт кнопка «Поделиться»
# в мобильных приложениях, то есть приходить будут в основном они
_SHORTENERS = ("go.2gis.com", "maps.app.goo.gl", "goo.gl", "yandex.ru/maps/-/",
               "yandex.kz/maps/-/")

# Пара голых чисел: владелец мог скопировать координаты, а не ссылку.
# Здесь принят общечеловеческий порядок «широта, долгота».
_RAW = re.compile(rf"^\s*{NUM}\s*,\s*{NUM}\s*$")


def _service(url: str) -> str | None:
    for marker, name in _HOSTS.items():
        if marker in url:
            return name
    return None


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def parse_place_link(url: str) -> tuple[float, float, str] | None:
    """(широта, долгота, откуда) из ссылки. None — координат в ней нет."""
    text = unquote(url.strip())

    if (raw := _RAW.match(text)) is not None:
        lat, lon = float(raw.group(1)), float(raw.group(2))
        return (lat, lon, "координаты") if _valid(lat, lon) else None

    name = _service(text)
    # если сервис не опознан, пробуем все выражения — ссылка могла прийти
    # с зеркала или сокращателя, который мы не знаем
    services = [name] if name else list(_PATTERNS)

    for service in services:
        for pattern, lat_first in _PATTERNS[service]:
            if (found := pattern.search(text)) is None:
                continue
            first, second = float(found.group(1)), float(found.group(2))
            lat, lon = (first, second) if lat_first else (second, first)
            if _valid(lat, lon):
                return lat, lon, service
    return None


async def expand_short_link(url: str) -> str:
    """Развернуть короткую ссылку в полную. При ошибке вернуть исходную.

    Единственный запрос наружу во всей истории, и только в момент настройки:
    короткие адреса координат не содержат, а узнать их можно лишь пройдя по
    редиректу.
    """
    if not any(host in url for host in _SHORTENERS):
        return url
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                return str(response.url)
    except Exception:
        return url


def verify_url(lat: float, lon: float) -> str:
    """Ссылка «посмотреть, что получилось».

    Google Maps выбран не как источник, а как проверка: формат у него
    стабильный, и открывается он у всех. Сверять точку глазами — единственная
    защита от перепутанного порядка чисел.
    """
    return f"https://www.google.com/maps?q={lat},{lon}"
