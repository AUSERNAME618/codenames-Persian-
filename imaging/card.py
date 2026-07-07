"""
رسم یک کارت کدنیم (۵×۵ کارت روی برد).
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from imaging import theme
from imaging.shapes import paste_rounded_gradient, paste_rounded_solid

_STATE_COLORS = {
    "unrevealed": (theme.CARD_CREAM, theme.CARD_BORDER_CREAM),
    "neutral": (theme.CARD_CREAM, theme.CARD_BORDER_CREAM),
    "red": (theme.CARD_RED, theme.CARD_BORDER_RED),
    "blue": (theme.CARD_BLUE, theme.CARD_BORDER_BLUE),
    "assassin": (theme.CARD_ASSASSIN, theme.CARD_BORDER_ASSASSIN),
}


def _draw_corner_icon(canvas: Image.Image, box: tuple[int, int, int, int], border_color: str) -> None:
    x0, y0, x1, y1 = box
    icon_size = 34
    icon_margin = 12
    icon_x1 = x1 - icon_margin
    icon_y0 = y0 + icon_margin
    icon_x0 = icon_x1 - icon_size

    draw = ImageDraw.Draw(canvas)
    draw.line([icon_x0, icon_y0 - 6, icon_x1, icon_y0 - 6], fill=border_color, width=2)

    overlay = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([0, 0, icon_size - 1, icon_size - 1], radius=4, outline=border_color, width=2)
    od.ellipse([icon_size * 0.32, icon_size * 0.15, icon_size * 0.68, icon_size * 0.5], outline=border_color, width=2)
    od.arc([icon_size * 0.1, icon_size * 0.45, icon_size * 0.9, icon_size * 1.3], start=200, end=340, fill=border_color, width=2)
    canvas.alpha_composite(overlay, (icon_x0, icon_y0))


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


def draw_card(canvas: Image.Image, box: tuple[int, int, int, int], word: str, state: str) -> None:
    """
    state یکی از: 'unrevealed', 'red', 'blue', 'neutral', 'assassin'
    - unrevealed/neutral ظاهرشون یکسانه (کرم) چون قبل و بعد فاش‌شدنِ خنثی فرقی نداره
    - assassin: بدون لیبل سفید، متن مستقیم سفید روی کارت مشکی
    """
    grad, border = _STATE_COLORS[state]
    paste_rounded_gradient(canvas, box, grad[0], grad[1], theme.CARD_RADIUS, border_color=border, border_width=3)
    _draw_corner_icon(canvas, box, border)

    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    label_margin_x = 14
    label_h = int(h * 0.34)
    label_box = (x0 + label_margin_x, y1 - label_h - 10, x1 - label_margin_x, y1 - 10)

    draw = ImageDraw.Draw(canvas)
    if state == "assassin":
        text_color = theme.TEXT_WHITE
    else:
        paste_rounded_solid(canvas, label_box, theme.WHITE, radius=10, with_shadow=False)
        text_color = theme.TEXT_DARK

    font = ImageFont.truetype(theme.FONT_DEMIBOLD, 26, layout_engine=ImageFont.Layout.RAQM)
    lx0, ly0, lx1, ly1 = label_box
    cx, cy = (lx0 + lx1) // 2, (ly0 + ly1) // 2

    # اگه کلمه بلند بود، فونت رو کوچیک‌تر کن تا از لیبل بیرون نزنه
    max_w = (lx1 - lx0) - 16
    while font.getlength(word) > max_w and font.size > 14:
        font = ImageFont.truetype(font.path, font.size - 2, layout_engine=ImageFont.Layout.RAQM)

    draw.text((cx, cy), word, font=font, fill=text_color, anchor="mm")
