"""Отрисовка QR-кодов на сервере.

Кодирование живёт на бэкенде намеренно: гостевому бандлу не нужна
библиотека кодирования, браузер получает готовый SVG в пару килобайт.
"""

import io

import segno


def make_qr_svg(target: str, *, dark: str = "#2A211B") -> bytes:
    """SVG-код на переданный адрес.

    Уровень коррекции «m» — компромисс между плотностью и живучестью:
    наклейку на столе трут и заливают, часть модулей теряется.
    """
    buf = io.BytesIO()  # segno пишет SVG байтами, не строкой
    segno.make(target, error="m").save(
        buf, kind="svg", scale=1, border=2, dark=dark, light=None
    )
    return buf.getvalue()
