"""
توابع کمکی برای ترسیم: گرادیان مورب، مستطیل گردگوشه با سایه، تبدیل رنگ hex.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def diagonal_gradient(size: tuple[int, int], color_start: str, color_end: str) -> Image.Image:
    """یه گرادیان مورب (از گوشه‌ی بالا-چپ به پایین-راست) می‌سازه."""
    w, h = size
    start = np.array(hex_to_rgb(color_start), dtype=np.float32)
    end = np.array(hex_to_rgb(color_end), dtype=np.float32)

    # وزنِ هر پیکسل بر اساس فاصله‌ی مورب نرمال‌شده (۰ تا ۱)
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, h)
    xx, yy = np.meshgrid(x, y)
    t = (xx + yy) / 2.0
    t = t[..., np.newaxis]

    arr = start * (1 - t) + end * t
    arr = arr.astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """ماسک سیاه‌وسفید برای گردکردن گوشه‌ها."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def rounded_gradient_patch(
    size: tuple[int, int], color_start: str, color_end: str, radius: int
) -> Image.Image:
    """یه پچ RGBA گردگوشه با گرادیان مورب می‌سازه (برای پیست‌کردن روی کانواس اصلی)."""
    grad = diagonal_gradient(size, color_start, color_end).convert("RGBA")
    mask = rounded_mask(size, radius)
    grad.putalpha(mask)
    return grad


def draw_shadow(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    blur: int = 10,
    offset: tuple[int, int] = (0, 6),
    opacity: int = 90,
) -> None:
    """
    یه سایه‌ی نرم زیر یه مستطیل گردگوشه روی canvas (RGBA) می‌کشه.
    box = (x0, y0, x1, y1) همون محل نهایی شکل (نه سایه).
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    pad = blur * 3

    shadow_layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.rounded_rectangle(
        [pad, pad, pad + w, pad + h], radius=radius, fill=(0, 0, 0, opacity)
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))

    paste_x = x0 - pad + offset[0]
    paste_y = y0 - pad + offset[1]
    canvas.alpha_composite(shadow_layer, (paste_x, paste_y))


def paste_rounded_gradient(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    color_start: str,
    color_end: str,
    radius: int,
    border_color: str | None = None,
    border_width: int = 3,
    with_shadow: bool = True,
) -> None:
    """سایه (اختیاری) + پچ گرادیانِ گردگوشه + حاشیه (اختیاری) رو روی canvas می‌ذاره."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0

    if with_shadow:
        draw_shadow(canvas, box, radius)

    patch = rounded_gradient_patch((w, h), color_start, color_end, radius)
    canvas.alpha_composite(patch, (x0, y0))

    if border_color:
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            [x0, y0, x1 - 1, y1 - 1], radius=radius, outline=border_color, width=border_width
        )


def paste_rounded_solid(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    color: str,
    radius: int,
    with_shadow: bool = True,
) -> None:
    """مثل paste_rounded_gradient ولی با رنگ یکدست (نه گرادیان) - برای پنل‌ها و لیبل‌های سفید."""
    paste_rounded_gradient(canvas, box, color, color, radius, with_shadow=with_shadow)
