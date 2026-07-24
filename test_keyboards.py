import json
import sys

from game.state import Game, Team, Role
from game.idgen import generate_game_id
from keyboards.lobby import build_lobby_rows
from keyboards.board import build_board_rows


def assert_true(cond, msg):
    if not cond:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ OK: {msg}")


def print_rows(rows, title):
    print(f"\n--- {title} ---")
    for row in rows:
        print(" | ".join(b.text for b in row))


def main():
    words = json.load(open("data/words_fa.json", encoding="utf-8"))
    g = Game(game_id=generate_game_id(), chat_id=1, host_id=100, team_size_mode=4)

    # --- تست لابی خالی (۴ نفره) ---
    rows = build_lobby_rows(g)
    assert_true(len(rows) == 7, "لابی حالت ۴نفره باید ۷ ردیف باشه")
    assert_true(rows[0][2].text == "🔵 تیم آبی", "راستِ ردیف اول باید تیم آبی باشه")
    assert_true(rows[0][0].text == "🔴 تیم قرمز", "چپِ ردیف اول باید تیم قرمز باشه")
    assert_true("خالی" in rows[3][0].text, "اسلات مامور قرمز خالی باید 'خالی' نشون بده")
    print_rows(rows, "لابی خالی - ۴نفره")

    # --- تست بعد از پرشدن یه اسلات ---
    g.join_slot(1, "Ali", Team.RED, Role.OPERATIVE, slot=0)
    rows = build_lobby_rows(g)
    assert_true("Ali" in rows[3][0].text, "بعد از join، اسم علی باید روی دکمه بیاد")

    # --- تست حالت ۸نفره: باید ۳ ردیف اسلات مامور داشته باشه ---
    g.cycle_team_size()  # 6
    g.cycle_team_size()  # 8
    rows = build_lobby_rows(g)
    # انتظار: هدر + رنگ + برچسب‌مامور + ۳ردیف‌مامور + برچسب‌جاسوس + ۱ردیف‌جاسوس + فوتر = ۹
    assert_true(len(rows) == 9, f"لابی حالت ۸نفره باید ۹ ردیف باشه، شد {len(rows)}")
    print_rows(rows, "لابی - ۸نفره")

    # --- تست کیبورد بازی ---
    g.cycle_team_size()  # -> 4 (برگردیم ساده)
    g.join_slot(1, "Ali", Team.RED, Role.SPYMASTER, slot=0)
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)
    g.join_slot(3, "Sara", Team.BLUE, Role.SPYMASTER, slot=0)
    g.join_slot(4, "Neda", Team.BLUE, Role.OPERATIVE, slot=0)
    g.start_game(words)

    board_rows_operative = build_board_rows(g, Role.OPERATIVE)
    board_rows_spymaster = build_board_rows(g, Role.SPYMASTER)

    assert_true(len(board_rows_operative) == 11, "پنل بازی باید ۱۱ ردیف باشه (شامل ردیف انتقال به آخرین پیام)")
    assert_true(len(board_rows_operative[-1]) == 1, "ردیف آخر باید فقط دکمه‌ی انتقال به آخرین پیام باشه")
    assert_true(len(board_rows_operative[-2]) == 2, "ردیف ماقبل‌آخر باید ۲ دکمه (پایان دست/اتمام حدس) داشته باشه")
    assert_true(len(board_rows_operative[0]) == 3, "ردیف‌های کلمه باید ۳تایی باشن")

    # مامور نباید هیچ ایموجی رنگی ببینه (چون هنوز هیچی فاش نشده)
    any_color_visible_to_operative = any(
        any(e in btn.text for e in ["🟥", "🟦", "⬜", "⬛"])
        for row in board_rows_operative[:8]
        for btn in row
    )
    assert_true(not any_color_visible_to_operative, "مامور نباید قبل از حدس، رنگی ببینه")

    # جاسوس باید همه‌ی ۲۵ تا رو رنگی ببینه
    all_color_visible_to_spymaster = all(
        any(e in btn.text for e in ["🟥", "🟦", "⬜", "⬛"])
        for row in board_rows_spymaster[:8]
        for btn in row
    ) and any(e in board_rows_spymaster[8][1].text for e in ["🟥", "🟦", "⬜", "⬛"])
    assert_true(all_color_visible_to_spymaster, "جاسوس باید همه‌ی ۲۵ خونه رو رنگی ببینه")

    print_rows(board_rows_spymaster, "پنل بازی - دید جاسوس (رنگی)")
    print_rows(board_rows_operative, "پنل بازی - دید مامور (بدون رنگ)")

    # --- بعد از یه حدس درست، مامور هم باید رنگ همون خونه رو ببینه ---
    idx_correct = next(
        i for i, c in enumerate(g.board)
        if c.color.value == g.current_turn.value and not c.revealed
    )
    g.set_clue_count(1)
    g.guess(idx_correct, "تستی")
    board_rows_operative_after = build_board_rows(g, Role.OPERATIVE)
    r, c = divmod(idx_correct, 3) if idx_correct < 24 else (8, 1)
    revealed_btn_text = board_rows_operative_after[r][c].text
    assert_true(
        any(e in revealed_btn_text for e in ["🟥", "🟦", "⬜", "⬛"]),
        "بعد از حدس درست، مامور هم باید رنگ همون خونه رو ببینه",
    )

    print("\n🎉 همه‌ی تست‌های کیبورد رد شدن.")


if __name__ == "__main__":
    main()
