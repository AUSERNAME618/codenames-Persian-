"""
رسم پنل کناری یک تیم (آبی یا قرمز).
side='left'  -> اسم تیم گوشه‌ی بالا-چپ، شمارنده‌ی کارت گوشه‌ی بالا-راست (پنل آبی، سمت چپ تخته)
side='right' -> اسم تیم گوشه‌ی بالا-راست، شمارنده‌ی کارت گوشه‌ی بالا-چپ (پنل قرمز، سمت راست تخته)
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from imaging import theme
from imaging.shapes import paste_rounded_solid


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def draw_team_panel(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    panel_color: str,
    team_label: str,
    cards_remaining: int,
    operative_names: list[str],
    spymaster_name: str | None,
    side: str,
) -> None:
    x0, y0, x1, y1 = box
    paste_rounded_solid(canvas, box, panel_color, radius=theme.PANEL_RADIUS)
    draw = ImageDraw.Draw(canvas)
    pad = 22
    center_x = (x0 + x1) // 2

    name_font = _font(theme.FONT_BLACK, 34)
    count_font = _font(theme.FONT_EXTRABOLD, 28)
    label_font = _font(theme.FONT_EXTRABOLD, 29)
    name_list_font = _font(theme.FONT_MEDIUM, 22)

    label_color = theme.BLACK

    # --- اسم تیم + بج شمارنده در دو گوشه‌ی بالا (قرینه بر اساس side) ---
    badge_size = 52
    badge_y0 = y0 + pad

    if side == "left":
        draw.text((x0 + pad, y0 + pad), team_label, font=name_font, fill=theme.WHITE, anchor="la")
        badge_x0 = x1 - pad - badge_size
    else:
        draw.text((x1 - pad, y0 + pad), team_label, font=name_font, fill=theme.WHITE, anchor="ra")
        badge_x0 = x0 + pad

    badge_box = (badge_x0, badge_y0, badge_x0 + badge_size, badge_y0 + badge_size)
    paste_rounded_solid(canvas, badge_box, theme.WHITE, radius=badge_size // 2, with_shadow=True)
    bcx, bcy = badge_x0 + badge_size // 2, badge_y0 + badge_size // 2
    draw.text((bcx, bcy), str(cards_remaining), font=count_font, fill=panel_color, anchor="mm")

    y = y0 + pad + 70

    # --- مامورین حدس ---
    draw.text((center_x, y), "مامورین حدس", font=label_font, fill=label_color, anchor="ma")
    y += 46
    if operative_names:
        for name in operative_names[:3]:
            draw.text((center_x, y), name, font=name_list_font, fill=theme.WHITE, anchor="ma")
            y += 34
    else:
        draw.text((center_x, y), "—", font=name_list_font, fill=theme.WHITE, anchor="ma")
        y += 34
    y += 20

    # --- جاسوس ---
    draw.text((center_x, y), "جاسوس", font=label_font, fill=label_color, anchor="ma")
    y += 46
    draw.text((center_x, y), spymaster_name or "—", font=name_list_font, fill=theme.WHITE, anchor="ma")


def draw_guess_log_below_panel(
    canvas: Image.Image,
    panel_box: tuple[int, int, int, int],
    log_color: str,
    guess_log: list[tuple[str, str]],
    canvas_height: int,
) -> None:
    """
    لاگ حدس‌های این تیم رو *زیرِ* پنل رنگی (نه داخلش) می‌نویسه.
    برای خوانایی روی هر سه پس‌زمینه‌ی ممکن (آبی/قرمز/طوسیِ باخت)، متن سفید با حاشیه‌ی
    مشکیِ نازکه، نه رنگ خودِ تیم (که روی پس‌زمینه‌ی هم‌رنگ محو می‌شد).
    جدیدترین حدس همیشه بالای لیست (نزدیک‌تر به پنل) قرار می‌گیره.
    وقتی به ته عکس برسه، قدیمی‌ترین‌ها به‌طور خودکار از لیست بیرون می‌مونن.
    """
    x0, _, x1, y1 = panel_box
    center_x = (x0 + x1) // 2
    font = _font(theme.FONT_DEMIBOLD, 23)
    line_h = 34
    y = y1 + 18
    max_y = canvas_height - 16

    available_lines = max(0, (max_y - y) // line_h)
    if available_lines == 0 or not guess_log:
        return

    recent = guess_log[-available_lines:]
    ordered = list(reversed(recent))  # جدیدترین اول (بالا)

    draw = ImageDraw.Draw(canvas)
    for player_name, word in ordered:
        text = f"({player_name}:{word})"
        draw.text(
            (center_x, y), text, font=font,
            fill=theme.LOG_TEXT_COLOR, stroke_width=2, stroke_fill=theme.LOG_STROKE_COLOR,
            anchor="ma",
        )
        y += line_h
