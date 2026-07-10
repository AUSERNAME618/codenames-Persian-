"""
ترکیب نهایی تصویر پنل بازی: گرید کارت‌ها، پنل‌های تیم، لاگ حدس، شماره‌ی راند/بنر برنده، نوار سرنخ.

پس‌زمینه سه حالت داره:
- نوبت تیم آبی در جریانه -> آبی
- نوبت تیم قرمز در جریانه -> قرمز/نارنجی
- بازی با کارت قاتل تموم شده -> طوسی (صرف‌نظر از اینکه کدوم تیم برنده شده)
- بازی عادی (بدون قاتل) تموم شده -> رنگ تیم برنده
"""
from __future__ import annotations

from PIL import ImageDraw, ImageFont

from imaging import theme
from imaging.shapes import diagonal_gradient, paste_rounded_solid, hex_to_rgb
from imaging.card import draw_card, draw_guessed_mark
from imaging.panel import draw_team_panel, draw_guess_log_below_panel


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


_TEAM_FA = {"red": "قرمز", "blue": "آبی"}


def render_board(
    cards: list[dict],
    current_turn: str,
    round_number: int,
    red_cards_remaining: int,
    blue_cards_remaining: int,
    red_operatives: list[str],
    blue_operatives: list[str],
    red_spymaster: str | None,
    blue_spymaster: str | None,
    red_guess_log: list[tuple[str, str]],
    blue_guess_log: list[tuple[str, str]],
    clue_word: str | None,
    clue_number: int | None,
    clue_stars: int = 0,
    winner: str | None = None,
    ended_by_assassin: bool = False,
    winner_players: list[str] | None = None,
    show_guess_log: bool = True,
):
    """
    cards: لیست ۲۵تایی از دیکشنری {"word": str, "state": "unrevealed"|"red"|"blue"|"neutral"|"assassin"}
    current_turn: "red" یا "blue" (وقتی بازی هنوز تموم نشده، رنگ پس‌زمینه رو تعیین می‌کنه)
    winner: "red"/"blue"/None -> اگه ست شده باشه، بنر برنده به‌جای شماره‌ی راند نشون داده می‌شه
    ended_by_assassin: اگه True، پس‌زمینه صرف‌نظر از برنده، طوسی می‌شه
    show_guess_log: برای عکس جاسوس (که فقط یه‌بار اول بازی فرستاده می‌شه) False بذار
    خروجی: تصویر نهایی (PIL Image، حالت RGB)
    """
    outer = 20
    gap = 40
    guess_log_extra = 300

    panel_w = theme.PANEL_W
    grid_w = theme.GRID_COLS * theme.CARD_W + (theme.GRID_COLS - 1) * theme.CARD_GAP
    grid_h = theme.GRID_ROWS * theme.CARD_H + (theme.GRID_ROWS - 1) * theme.CARD_GAP

    canvas_w = outer * 2 + panel_w * 2 + gap * 2 + grid_w
    canvas_h = theme.MARGIN_TOP + grid_h + theme.MARGIN_BOTTOM + guess_log_extra

    # --- انتخاب پس‌زمینه ---
    if winner is not None and ended_by_assassin:
        bg = theme.BG_GRAY_ASSASSIN
    elif winner is not None:
        bg = theme.BG_BLUE_TURN if winner == "blue" else theme.BG_RED_TURN
    else:
        bg = theme.BG_BLUE_TURN if current_turn == "blue" else theme.BG_RED_TURN

    canvas = diagonal_gradient((canvas_w, canvas_h), bg[0], bg[1]).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # --- بالای تصویر: یا شماره‌ی راند، یا بنرِ برنده ---
    if winner is not None:
        banner_font = _font(theme.FONT_BLACK, 50)
        draw.text(
            (canvas_w // 2, 22),
            f"🏆 تیم {_TEAM_FA[winner]} برنده شد",
            font=banner_font, fill=theme.WHITE, anchor="ma",
        )
        if winner_players:
            names_font = _font(theme.FONT_MEDIUM, 26)
            draw.text(
                (canvas_w // 2, 86),
                "  ،  ".join(winner_players),
                font=names_font, fill=theme.WHITE, anchor="ma",
            )
    else:
        round_font = _font(theme.FONT_BLACK, 44)
        draw.text((canvas_w // 2, 30), f"راند {round_number}", font=round_font, fill=theme.WHITE, anchor="ma")

    # --- محاسبه‌ی محل پنل‌ها و گرید ---
    blue_box = (outer, theme.MARGIN_TOP, outer + panel_w, theme.MARGIN_TOP + grid_h)
    grid_x0 = outer + panel_w + gap
    grid_box = (grid_x0, theme.MARGIN_TOP, grid_x0 + grid_w, theme.MARGIN_TOP + grid_h)
    red_x0 = grid_x0 + grid_w + gap
    red_box = (red_x0, theme.MARGIN_TOP, red_x0 + panel_w, theme.MARGIN_TOP + grid_h)

    # --- پنل‌های تیم ---
    draw_team_panel(
        canvas, blue_box, theme.PANEL_BLUE, "تیم آبی", blue_cards_remaining,
        blue_operatives, blue_spymaster, side="left",
    )
    draw_team_panel(
        canvas, red_box, theme.PANEL_RED, "تیم قرمز", red_cards_remaining,
        red_operatives, red_spymaster, side="right",
    )

    # --- لاگ حدس زیر هر پنل (اختیاری - برای عکس جاسوس خاموشه) ---
    if show_guess_log:
        draw_guess_log_below_panel(canvas, blue_box, theme.PANEL_BLUE, blue_guess_log, canvas_h)
        draw_guess_log_below_panel(canvas, red_box, theme.PANEL_RED, red_guess_log, canvas_h)

    # --- گرید ۵×۵ کارت‌ها ---
    gx0, gy0, gx1, gy1 = grid_box
    for i, card in enumerate(cards):
        r, c = divmod(i, theme.GRID_COLS)
        cx0 = gx0 + c * (theme.CARD_W + theme.CARD_GAP)
        cy0 = gy0 + r * (theme.CARD_H + theme.CARD_GAP)
        draw_card(canvas, (cx0, cy0, cx0 + theme.CARD_W, cy0 + theme.CARD_H), card["word"], card["state"])

    # --- نوار سرنخ پایین: [مستطیل بلندِ کلمه] سپس [مربع عدد] (کلمه چپ‌تر، عدد راست‌تر) ---
    bar_y0 = gy1 + 30
    bar_h = 64
    num_size = 64
    word_w = 360
    total_w = word_w + 14 + num_size
    bar_x0 = gx0 + (grid_w - total_w) // 2

    word_box = (bar_x0, bar_y0, bar_x0 + word_w, bar_y0 + bar_h)
    num_box = (bar_x0 + word_w + 14, bar_y0, bar_x0 + word_w + 14 + num_size, bar_y0 + bar_h)

    paste_rounded_solid(canvas, word_box, theme.WHITE, radius=16)
    paste_rounded_solid(canvas, num_box, theme.WHITE, radius=16)

    clue_font = _font(theme.FONT_EXTRABOLD, 32)
    wcx, wcy = (word_box[0] + word_box[2]) // 2, (word_box[1] + word_box[3]) // 2
    clue_display = (clue_word or "") + ("*" * clue_stars)
    draw.text((wcx, wcy), clue_display, font=clue_font, fill=theme.TEXT_DARK, anchor="mm")
    ncx, ncy = (num_box[0] + num_box[2]) // 2, (num_box[1] + num_box[3]) // 2
    draw.text((ncx, ncy), str(clue_number) if clue_number is not None else "", font=clue_font, fill=theme.TEXT_DARK, anchor="mm")

    return canvas.convert("RGB")


def render_spymaster_board(cards: list[dict]) -> "Image":
    """
    عکس ساده‌ی مخصوص جاسوس: فقط گرید ۵×۵ با رنگ واقعی کارت‌ها، پس‌زمینه‌ی طوسی ثابت
    (نه بسته به نوبت)، بدون پنل تیم و بدون لاگ حدس.
    این عکس فقط یک‌بار در ابتدای بازی فرستاده می‌شه و بعد از هر حدس، دوباره (آپدیت‌شده
    با ضربدر روی کارت‌های حدس‌زده‌شده) به‌جاش فرستاده می‌شه.

    cards: لیست ۲۵تایی {"word": str, "state": رنگ واقعی کارت, "guessed_by": "red"|"blue"|None}
    """
    outer = 30
    grid_w = theme.GRID_COLS * theme.CARD_W + (theme.GRID_COLS - 1) * theme.CARD_GAP
    grid_h = theme.GRID_ROWS * theme.CARD_H + (theme.GRID_ROWS - 1) * theme.CARD_GAP
    canvas_w = grid_w + outer * 2
    canvas_h = grid_h + outer * 2

    bg = theme.BG_GRAY_ASSASSIN
    canvas = diagonal_gradient((canvas_w, canvas_h), bg[0], bg[1]).convert("RGBA")

    mark_rgb = {
        "red": hex_to_rgb(theme.PANEL_RED),
        "blue": hex_to_rgb(theme.PANEL_BLUE),
    }

    for i, card in enumerate(cards):
        r, c = divmod(i, theme.GRID_COLS)
        x0 = outer + c * (theme.CARD_W + theme.CARD_GAP)
        y0 = outer + r * (theme.CARD_H + theme.CARD_GAP)
        box = (x0, y0, x0 + theme.CARD_W, y0 + theme.CARD_H)
        draw_card(canvas, box, card["word"], card["state"])
        guessed_by = card.get("guessed_by")
        if guessed_by in mark_rgb:
            draw_guessed_mark(canvas, box, mark_rgb[guessed_by])

    return canvas.convert("RGB")