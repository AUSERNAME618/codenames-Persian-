"""
چیدمان کیبورد لابی (پیش از شروع بازی).
ساختار پایه (حالت ۴نفره) = ۷ ردیف:
  ۱) هدر تیم‌ها
  ۲) نوار رنگ تیم (تزئینی)
  ۳) برچسب «مامور حدس»
  ۴) اسلات(های) مامور  <- به تعداد op_limit ردیف (۱، ۲ یا ۳ تا)
  ۵) برچسب «جاسوس»
  ۶) اسلات(های) جاسوس  <- همیشه ۱ ردیف (طبق تنظیمات فعلی)
  ۷) فوتر: تغییر نفرات / شروع بازی / خروج

راست=آبی، چپ=قرمز در همه‌ی ردیف‌ها (طبق خواسته‌ی کاربر)، وسط همیشه ستون خنثی/خالی.
"""
from __future__ import annotations

from game.state import Game, Team, Role
from keyboards.types import ButtonSpec, Rows

_EMPTY_OPERATIVE = "🤵 خالی"
_EMPTY_SPYMASTER = "🕵️ خالی"


def _find_player(game: Game, team: Team, role: Role, slot: int):
    return next(
        (
            p
            for p in game.players.values()
            if p.team == team and p.role == role and p.slot == slot
        ),
        None,
    )


def build_lobby_rows(game: Game) -> Rows:
    gid = game.game_id
    op_limit = game.max_operatives_per_team()
    sm_limit = game.max_spymasters_per_team()

    rows: Rows = []

    # ردیف ۱: هدر تیم‌ها (چپ=قرمز، وسط=برچسب، راست=آبی)
    rows.append(
        [
            ButtonSpec(text="🔴 تیم قرمز", callback_data="noop", style="danger"),
            ButtonSpec(text="➡️ تیم‌ها ⬅️", callback_data="noop"),
            ButtonSpec(text="🔵 تیم آبی", callback_data="noop", style="primary"),
        ]
    )

    # ردیف ۲: نوار رنگ (تزئینی)
    rows.append(
        [
            ButtonSpec(text="🔴 🔴 🔴", callback_data="noop", style="danger"),
            ButtonSpec(text="・", callback_data="noop"),
            ButtonSpec(text="🔵 🔵 🔵", callback_data="noop", style="primary"),
        ]
    )

    # ردیف ۳: برچسب «مامور حدس»
    rows.append(
        [
            ButtonSpec(text="مامور حدس ⬇️", callback_data="noop", style="danger"),
            ButtonSpec(text="・", callback_data="noop"),
            ButtonSpec(text="مامور حدس ⬇️", callback_data="noop", style="primary"),
        ]
    )

    # ردیف(های) اسلات مامور - یکی به ازای هر اسلات
    for slot in range(op_limit):
        red_p = _find_player(game, Team.RED, Role.OPERATIVE, slot)
        blue_p = _find_player(game, Team.BLUE, Role.OPERATIVE, slot)
        red_text = f"🤵 {red_p.name}" if red_p else _EMPTY_OPERATIVE
        blue_text = f"🤵 {blue_p.name}" if blue_p else _EMPTY_OPERATIVE
        rows.append(
            [
                ButtonSpec(
                    text=red_text,
                    callback_data=f"lobby:{gid}:join:{Team.RED.value}:{Role.OPERATIVE.value}:{slot}",
                    style="danger",
                ),
                ButtonSpec(text="・", callback_data="noop"),
                ButtonSpec(
                    text=blue_text,
                    callback_data=f"lobby:{gid}:join:{Team.BLUE.value}:{Role.OPERATIVE.value}:{slot}",
                    style="primary",
                ),
            ]
        )

    # ردیف برچسب «جاسوس»
    rows.append(
        [
            ButtonSpec(text="جاسوس ⬇️", callback_data="noop", style="danger"),
            ButtonSpec(text="・", callback_data="noop"),
            ButtonSpec(text="جاسوس ⬇️", callback_data="noop", style="primary"),
        ]
    )

    # ردیف(های) اسلات جاسوس
    for slot in range(sm_limit):
        red_p = _find_player(game, Team.RED, Role.SPYMASTER, slot)
        blue_p = _find_player(game, Team.BLUE, Role.SPYMASTER, slot)
        red_text = f"🕵️ {red_p.name}" if red_p else _EMPTY_SPYMASTER
        blue_text = f"🕵️ {blue_p.name}" if blue_p else _EMPTY_SPYMASTER
        rows.append(
            [
                ButtonSpec(
                    text=red_text,
                    callback_data=f"lobby:{gid}:join:{Team.RED.value}:{Role.SPYMASTER.value}:{slot}",
                    style="danger",
                ),
                ButtonSpec(text="・", callback_data="noop"),
                ButtonSpec(
                    text=blue_text,
                    callback_data=f"lobby:{gid}:join:{Team.BLUE.value}:{Role.SPYMASTER.value}:{slot}",
                    style="primary",
                ),
            ]
        )

    # ردیف آخر: چپ=تغییر نفرات، وسط=شروع بازی، راست=خروج
    rows.append(
        [
            ButtonSpec(text="🔁 تغییر نفرات", callback_data=f"lobby:{gid}:cycle"),
            ButtonSpec(text="✅ شروع بازی", callback_data=f"lobby:{gid}:start", style="success"),
            ButtonSpec(text="🚪 خروج", callback_data=f"lobby:{gid}:exit", style="danger"),
        ]
    )

    return rows
