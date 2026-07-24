"""
توابع کمکی برای ترسیم: گرادیان مورب، مستطیل گردگوشه با سایه، تبدیل رنگ hex.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def lighten_hex(hex_color: str, factor: float) -> str:
    """رنگ رو به سمت سفید روشن‌تر می‌کنه (factor بین ۰ تا ۱)."""
    r, g, b = hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return rgb_to_hex((min(r, 255), min(g, 255), min(b, 255)))


def darken_hex(hex_color: str, factor: float) -> str:
    """رنگ رو به سمت سیاه تیره‌تر می‌کنه (factor بین ۰ تا ۱)."""
    r, g, b = hex_to_rgb(hex_color)
    r = int(r * (1 - factor))
    g = int(g * (1 - factor))
    b = int(b * (1 - factor))
    return rgb_to_hex((max(r, 0), max(g, 0), max(b, 0)))


@lru_cache(maxsize=128)
def diagonal_gradient(size: tuple[int, int], color_start: str, color_end: str) -> Image.Image:
    """یه گرادیان مورب (از گوشه‌ی بالا-چپ به پایین-راست) می‌سازه.
    نتیجه کش می‌شه چون خیلی از شکل‌ها (مثلاً همه‌ی کارت‌های یه رنگ، یا لیبلِ سفیدِ
    همه‌ی کارت‌ها) دقیقاً همون اندازه و همون دو رنگ رو دارن - این‌طوری محاسبه‌ی
    numpy فقط یه‌بار به‌ازای هر ترکیبِ اندازه/رنگ انجام می‌شه، نه به‌ازای هر کارت."""
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


@lru_cache(maxsize=64)
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """ماسک سیاه‌وسفید برای گردکردن گوشه‌ها. کش می‌شه چون اندازه/شعاعِ محدودی تکرار می‌شن."""
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


@lru_cache(maxsize=8)
def _vignette_layers(w: int, h: int, strength: int) -> tuple[Image.Image, Image.Image]:
    """محاسبه‌ی لایه‌های وینیت فقط به اندازه‌ی تصویر بستگی داره (نه به رنگِ پس‌زمینه)،
    پس کش می‌شه تا هر رندر دوباره از صفر محاسبه نشه."""
    x = np.linspace(-1, 1, w)
    y = np.linspace(-1, 1, h)
    xx, yy = np.meshgrid(x, y)

    highlight_dist = np.sqrt(xx**2 + (yy + 0.35) ** 2)
    highlight = np.clip(1 - highlight_dist, 0, 1) ** 2

    corner_dist = np.sqrt(xx**2 + yy**2)
    vignette = np.clip(corner_dist - 0.55, 0, 1)

    white_alpha = (highlight * strength).astype(np.uint8)
    white_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    white_layer.putalpha(Image.fromarray(white_alpha, mode="L"))

    black_alpha = np.clip(vignette * strength * 1.3, 0, 255).astype(np.uint8)
    black_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black_layer.putalpha(Image.fromarray(black_alpha, mode="L"))

    return white_layer, black_layer


def add_soft_vignette(canvas: Image.Image, strength: int = 16) -> None:
    """
    یه نورِ نرمِ استودیویی (ambient) به کل پس‌زمینه اضافه می‌کنه: یه های‌لایتِ ملایم
    نزدیکِ بالا-وسط، و یه تیرگیِ خیلی خفیف نزدیکِ گوشه‌ها (وینیت). شدت پایینه که
    خوانایی و کنتراستِ رنگ‌های تیم رو خراب نکنه.
    """
    w, h = canvas.size
    white_layer, black_layer = _vignette_layers(w, h, strength)
    canvas.alpha_composite(white_layer, (0, 0))
    canvas.alpha_composite(black_layer, (0, 0))


@lru_cache(maxsize=8)
def _dot_pattern_layer(
    w: int, h: int, spacing: int, dot_radius: float, opacity: int
) -> Image.Image:
    """
    یه لایه‌ی RGBA با شبکه‌ای از نقطه‌های کوچیکِ سفیدِ کمرنگ می‌سازه (شبیهِ پترنِ
    نقطه‌ای که کاربر نمونه‌اش رو فرستاد). فقط به اندازه‌ی تصویر بستگی داره، پس کش می‌شه.
    """
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    r = dot_radius
    y = spacing / 2
    while y < h:
        x = spacing / 2
        while x < w:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, opacity))
            x += spacing
        y += spacing
    return layer


def add_dot_pattern(
    canvas: Image.Image, spacing: int = 46, dot_radius: float = 2.4, opacity: int = 40
) -> None:
    """
    یه پترنِ ظریفِ نقطه‌نقطه (مثل نمونه‌ی کاربر) روی کل تصویر می‌کشه. باید بلافاصله
    بعدِ ساختِ گرادیانِ پس‌زمینه صدا زده بشه (قبل از پنل‌ها/کارت‌ها) تا فقط توی
    قسمت‌های خالیِ پس‌زمینه دیده بشه و زیرِ عناصرِ جلو پنهان بمونه.
    """
    w, h = canvas.size
    layer = _dot_pattern_layer(w, h, spacing, dot_radius, opacity)
    canvas.alpha_composite(layer, (0, 0))


def draw_shadow(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    blur: int = 16,
    offset: tuple[int, int] = (0, 9),
    opacity: int = 70,
) -> None:
    """
    یه سایه‌ی نرم و محیطی (ambient) زیر یه مستطیل گردگوشه روی canvas (RGBA) می‌کشه.
    box = (x0, y0, x1, y1) همون محل نهایی شکل (نه سایه).
    مقادیر پیش‌فرض برای حسِ کلی‌مورفیسم/نئومورفیسم تنظیم شدن: بلور زیاد، افستِ کم،
    شفافیتِ متوسط (نه سایه‌ی تیره و تند).
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


def add_top_gloss(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    max_opacity: int = 42,
    height_fraction: float = 0.5,
) -> None:
    """
    یه های‌لایتِ نرمِ سفید (گلاسمورفیسم/کلی‌مورفیسم) روی نیمه‌ی بالاییِ شکل می‌کشه که
    از بالا محو می‌شه به سمت پایین - شبیه نورِ استودیوییِ پخش‌شده که از بالا می‌تابه،
    بدون اینکه سطح "براق و پلاستیکی" به نظر برسه.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return

    fade_h = max(1, int(h * height_fraction))
    grad_col = np.zeros((fade_h, 1), dtype=np.uint8)
    for yy in range(fade_h):
        t = yy / fade_h
        # منحنیِ نرم (نه خطی) برای محوشدنِ طبیعی‌تر
        grad_col[yy, 0] = int(max_opacity * (1 - t) ** 1.6)
    alpha_col = np.vstack([grad_col, np.zeros((h - fade_h, 1), dtype=np.uint8)])
    alpha_full = np.repeat(alpha_col, w, axis=1)

    mask_img = rounded_mask((w, h), radius)
    mask_arr = np.array(mask_img, dtype=np.uint16)
    combined = (alpha_full.astype(np.uint16) * mask_arr // 255).astype(np.uint8)

    gloss = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    gloss.putalpha(Image.fromarray(combined, mode="L"))
    canvas.alpha_composite(gloss, (x0, y0))


def add_rim_light(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    opacity: int = 60,
    width: int = 2,
) -> None:
    """
    به‌جای حاشیه‌ی سخت و پررنگِ قدیمی، یه خطِ نازکِ نیمه‌شفافِ سفید دورِ شکل می‌کشه
    تا لبه‌ها ظریف و شیشه‌ای به‌نظر برسن، بدون افکتِ "outline سنگین".
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [width / 2, width / 2, w - 1 - width / 2, h - 1 - width / 2],
        radius=max(1, radius - width // 2),
        outline=(255, 255, 255, opacity),
        width=width,
    )
    canvas.alpha_composite(overlay, (x0, y0))


def paste_rounded_gradient(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    color_start: str,
    color_end: str,
    radius: int,
    border_color: str | None = None,
    border_width: int = 3,
    with_shadow: bool = True,
    gloss: bool = True,
    rim_light: bool = True,
    gloss_opacity: int = 42,
) -> None:
    """سایه (اختیاری) + پچ گرادیانِ گردگوشه + گلاسِ نرمِ بالا + خطِ لبه‌ی ظریف رو روی canvas می‌ذاره.
    سبک کلی‌مورفیسم/نئومورفیسم: سایه‌ی محیطیِ نرم، گرادیانِ ملایم برای حسِ سه‌بعدی،
    های‌لایتِ شیشه‌ایِ ظریف بالای شکل، و لبه‌ی نازک به‌جای حاشیه‌ی سخت و پررنگ.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0

    if with_shadow:
        draw_shadow(canvas, box, radius)

    patch = rounded_gradient_patch((w, h), color_start, color_end, radius)
    canvas.alpha_composite(patch, (x0, y0))

    if gloss:
        add_top_gloss(canvas, box, radius, max_opacity=gloss_opacity)

    if rim_light:
        add_rim_light(canvas, box, radius)

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
