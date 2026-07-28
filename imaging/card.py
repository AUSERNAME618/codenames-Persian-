"""
رسم یک کارت کدنیم (۵×۵ کارت روی برد).

سبک: کلی‌مورفیسم (نرم، سه‌بعدی، مات) + نئومورفیسم (سایه‌ی محیطیِ ملایم، حسِ شناور) +
کمی گلاسمورفیسم (های‌لایتِ ظریفِ بالای هر کارت). به‌جای حاشیه‌ی سخت و پررنگ، از
لبه‌ی نازکِ نیمه‌شفاف استفاده می‌شه.

رندر به دو مرحله تقسیم شده تا سایه‌ی هیچ کارتی روی رویه‌ی کارتِ کناری‌اش ننشینه:
مرحله‌ی ۱ (draw_card_shadow) برای همه‌ی کارت‌های گرید اجرا می‌شه، بعد مرحله‌ی ۲
(draw_card_face) روی همه‌شون - این‌طوری هر رویه، هر سایه‌ای که زیرش نشسته رو کامل می‌پوشونه.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from imaging import theme
from imaging.shapes import (
    paste_rounded_gradient,
    paste_rounded_solid,
    draw_shadow,
    draw_bold_text,
    lighten_hex,
)
from imaging.text_safe import sanitize_for_font

_STATE_COLORS = {
    "unrevealed": (theme.CARD_CREAM, theme.CARD_BORDER_CREAM),
    "neutral": (theme.CARD_NEUTRAL_REVEALED, theme.CARD_BORDER_NEUTRAL_REVEALED),
    "red": (theme.CARD_RED, theme.CARD_BORDER_RED),
    "blue": (theme.CARD_BLUE, theme.CARD_BORDER_BLUE),
    "assassin": (theme.CARD_ASSASSIN, theme.CARD_BORDER_ASSASSIN),
}


def draw_card_shadow(canvas: Image.Image, box: tuple[int, int, int, int]) -> None:
    """سایه‌ی محیطیِ نرمِ کارت - همیشه قبل از رسمِ *همه‌ی* رویه‌های گرید صدا زده بشه."""
    draw_shadow(canvas, box, theme.CARD_RADIUS, blur=14, offset=(0, 7), opacity=65)


def _draw_corner_icon(canvas: Image.Image, box: tuple[int, int, int, int], border_color: str) -> None:
    x0, y0, x1, y1 = box
    icon_size = 42
    icon_margin = 18
    icon_x1 = x1 - icon_margin
    icon_y0 = y0 + icon_margin
    icon_x0 = icon_x1 - icon_size
    soft_color = (*_hex_to_rgb(border_color), 130)  # نیمه‌شفاف، هماهنگ با لحن ملایم

    draw = ImageDraw.Draw(canvas)
    draw.line([icon_x0, icon_y0 - 8, icon_x1, icon_y0 - 8], fill=soft_color, width=3)

    overlay = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([0, 0, icon_size - 1, icon_size - 1], radius=6, outline=soft_color, width=3)
    od.ellipse([icon_size * 0.32, icon_size * 0.15, icon_size * 0.68, icon_size * 0.5], outline=soft_color, width=3)
    od.arc([icon_size * 0.1, icon_size * 0.45, icon_size * 0.9, icon_size * 1.3], start=200, end=340, fill=soft_color, width=3)
    canvas.alpha_composite(overlay, (icon_x0, icon_y0))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def draw_guessed_mark(canvas: Image.Image, box: tuple[int, int, int, int], mark_color_rgb: tuple[int, int, int]) -> None:
    """
    یه ضربدر نیمه‌شفاف روی کارت می‌کشه (فقط برای عکس جاسوس) تا نشون بده این کارت
    قبلاً حدس زده شده، بدون اینکه کلمه‌ی زیرش کاملاً پوشیده بشه.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    pad = 10
    line_w = max(6, int(min(w, h) * 0.07))
    color = (*mark_color_rgb, 165)  # نیمه‌شفاف تا کلمه‌ی زیرش خونا بمونه
    od.line([pad, pad, w - pad, h - pad], fill=color, width=line_w)
    od.line([w - pad, pad, pad, h - pad], fill=color, width=line_w)
    canvas.alpha_composite(overlay, (x0, y0))


def draw_card_face(canvas: Image.Image, box: tuple[int, int, int, int], word: str, state: str) -> None:
    """
    رویه‌ی کارت (بدون سایه - سایه جدا و قبل از همه‌ی رویه‌ها با draw_card_shadow رسم می‌شه).

    state یکی از: 'unrevealed', 'red', 'blue', 'neutral', 'assassin'
    - unrevealed: کرم (رنگ مشترک همه‌ی کارت‌ها قبل از فاش‌شدن)
    - neutral: بعد از فاش‌شدن رنگ جدا (تیره‌تر از کرم) می‌گیره تا از حالت فاش‌نشده متمایز باشه
    - assassin: بدون لیبل سفید، متن مستقیم سفید روی کارت مشکی
    """
    grad, border = _STATE_COLORS[state]
    paste_rounded_gradient(canvas, box, grad[0], grad[1], theme.CARD_RADIUS, with_shadow=False)
    _draw_corner_icon(canvas, box, border)

    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    label_margin_x = 18
    label_h = int(h * 0.36)
    label_box = (x0 + label_margin_x, y1 - label_h - 14, x1 - label_margin_x, y1 - 14)

    if state == "assassin":
        text_color = theme.TEXT_WHITE
    else:
        # سطحِ لیبل هم یه گرادیانِ ماتِ خیلی ظریف بین سفید و بژِ خیلی روشن می‌گیره
        # تا کاملاً تخت/پلاستیکی به‌نظر نرسه (سازگار با حسِ کلی‌مورفیسم)
        paste_rounded_gradient(
            canvas, label_box, theme.WHITE, "#f3ede1", radius=16,
            with_shadow=False, gloss=False,
        )
        text_color = theme.TEXT_DARK

    safe_word = sanitize_for_font(word, theme.FONT_BLACK)
    font = ImageFont.truetype(theme.FONT_BLACK, 36, layout_engine=ImageFont.Layout.RAQM)
    lx0, ly0, lx1, ly1 = label_box
    cx, cy = (lx0 + lx1) // 2, (ly0 + ly1) // 2

    # اگه کلمه بلند بود، فونت رو کوچیک‌تر کن تا از لیبل بیرون نزنه
    max_w = (lx1 - lx0) - 24
    while font.getlength(safe_word) > max_w and font.size > 16:
        font = ImageFont.truetype(font.path, font.size - 2, layout_engine=ImageFont.Layout.RAQM)

    draw_bold_text(canvas, (cx, cy), safe_word, theme.FONT_BLACK, font.size, text_color, anchor="mm")


def draw_card(canvas: Image.Image, box: tuple[int, int, int, int], word: str, state: str) -> None:
    """میان‌بر تک‌مرحله‌ای (سایه + رویه با هم) - برای جاهایی که فقط یه کارت تنها رسم می‌شه.
    برای گریدِ ۵×۵ به‌جاش از draw_card_shadow + draw_card_face به‌صورت دو-پاس استفاده کن."""
    draw_card_shadow(canvas, box)
    draw_card_face(canvas, box, word, state)
