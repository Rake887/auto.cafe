"""Приём фотографий блюд: пережатие в WebP и хранение на диске.

Владелец снимает блюдо телефоном — это 3–5 МБ JPEG с ориентацией в EXIF.
Отдавать такое гостю на мобильном интернете нельзя, поэтому на входе всё
приводится к двум предсказуемым размерам.
"""

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# 160 — превью в списке блюд, 800 — крупное фото по тапу
SIZES = {"thumb": 160, "large": 800}
WEBP_QUALITY = 80


class PhotoTooBig(Exception):
    pass


class PhotoBroken(Exception):
    pass


def save_dish_photo(media_root: Path, dish_id: int, raw: bytes) -> str:
    """Сохранить фото блюда. Возвращает путь для image_url.

    Ключевая тонкость: `exif_transpose` — без него снимки с телефона лягут
    боком, потому что камера пишет поворот в EXIF, а не в пиксели.
    """
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PhotoTooBig()

    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except Exception as e:
        raise PhotoBroken() from e

    target_dir = media_root / "dishes"
    target_dir.mkdir(parents=True, exist_ok=True)

    for name, width in SIZES.items():
        resized = ImageOps.contain(image, (width, width), Image.LANCZOS)
        resized.save(
            target_dir / f"{dish_id}_{name}.webp", "WEBP", quality=WEBP_QUALITY
        )

    # версия в имени не нужна: файл перезаписывается, а ссылку обновляем
    # с меткой времени, чтобы браузер не показывал старую картинку
    return f"/api/media/dishes/{dish_id}_large.webp"


def delete_dish_photo(media_root: Path, dish_id: int) -> None:
    for name in SIZES:
        (media_root / "dishes" / f"{dish_id}_{name}.webp").unlink(missing_ok=True)
