"""
چیدمان کیبورد پنل بازی (حین بازی).
ساختار: ۸ ردیف اول = ۲۴ کلمه (۳ تایی)، ردیف ۹ = کلمه‌ی ۲۵ + دو برچسب تزئینی،
ردیف ۱۰ = دو دکمه‌ی واقعی (پایان دست / اتمام حدس).

دو حالت نمایش:
- جاسوس (spymaster): همیشه رنگ همه‌ی ۲۵ خانه رو می‌بینه (چون پیام PV خصوصیشه)
- مامور (operative)/گروه: فقط خانه‌های فاش‌شده رنگ نشون می‌دن، بقیه فقط متن خام
"""
from __future__ import annotations

from game.state import Game, Role, CardColor, GameStatus, Team
from keyboards.types import ButtonSpec, Rows

_COLOR_EMOJI = {
    CardColor.RED: "🟥",
    CardColor.BLUE: "🟦",
    CardColor.NEUTRAL: "⬜",
    CardColor.ASSASSIN: "⬛",
}

_TEAM_FA = {Team.RED: "🔴 قرمز", Team.BLUE: "🔵 آبی"}


def build_board_caption(game: Game) -> str:
    """متنی که بالای پنل بازی (روی خودِ پیام، نه دکمه‌ها) نشون داده می‌شه."""
    if game.status == GameStatus.FINISHED:
        if game.winner is not None:
            return f"🏆 تیم {_TEAM_FA[game.winner]} برنده شد"
        return "🏁 بازی تمام شد."

    team_name = _TEAM_FA[game.current_turn]
    if game.status == GameStatus.AWAITING_CLUE:
        return f"⏳ نوبت جاسوس تیم {team_name}"

    # GUESSING
    star_note = "*" * game.clue_stars
    clue_line = f"🔎 سرنخ: «{game.clue_word}{star_note}» ({game.clue_count})" if game.clue_word else ""
    progress = f"✅ حدس‌های درست: {game.correct_guesses_this_turn}/{game.clue_count}"
    return f"🎯 نوبت مامور تیم {team_name}\n{clue_line}\n{progress}"


def _cell_text(game: Game, idx: int, viewer_role: Role) -> str:
    card = game.board[idx]
    if viewer_role == Role.SPYMASTER or card.revealed:
        emoji = _COLOR_EMOJI[card.color]
        return f"{emoji} {card.word}"
    return card.word


def build_board_rows(game: Game, viewer_role: Role) -> Rows:
    gid = game.game_id

    def cell_button(idx: int) -> ButtonSpec:
        return ButtonSpec(
            text=_cell_text(game, idx, viewer_role),
            callback_data=f"board:{gid}:guess:{idx}",
        )

    rows: Rows = []

    # ردیف‌های ۱ تا ۸: ۲۴ کلمه، ۳تا در هر ردیف
    for r in range(8):
        row = [cell_button(r * 3 + c) for c in range(3)]
        rows.append(row)

    # ردیف ۹: چپ=برچسب تزئینی پایان دست، وسط=کلمه‌ی ۲۵ام، راست=برچسب تزئینی اتمام حدس
    rows.append(
        [
            ButtonSpec(text="پایان دست ⬇️", callback_data="noop", style="danger"),
            cell_button(24),
            ButtonSpec(text="اتمام حدس ⬇️", callback_data="noop", style="success"),
        ]
    )

    # ردیف ۱۰: دو دکمه‌ی واقعی و رنگی
    end_guess_text = "🟢 اتمام حدس"
    if game.clue_count > 0:
        end_guess_text = f"🟢 اتمام حدس ({game.correct_guesses_this_turn}/{game.clue_count})"

    rows.append(
        [
            ButtonSpec(text="🔴 پایان دست", callback_data=f"board:{gid}:endturn", style="danger"),
            ButtonSpec(text=end_guess_text, callback_data=f"board:{gid}:endguess", style="success"),
        ]
    )

    # ردیف ۱۱: انتقال دستیِ پنل به آخرین پیام چت (فقط سازنده‌ی بازی مجاز به کلیکه - چک تو هندلر)
    rows.append(
        [ButtonSpec(text="⬇️ انتقال به آخرین پیام", callback_data=f"board:{gid}:movebottom")]
    )

    return rows