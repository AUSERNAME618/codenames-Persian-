"""
تست دستی سریع برای منطق بازی (game/state.py).
اجرا: python3 test_state.py
"""
import json
import sys

from game.state import Game, Team, Role, GameStatus, GameError


def load_words():
    with open("data/words_fa.json", encoding="utf-8") as f:
        return json.load(f)


def assert_true(cond, msg):
    if not cond:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ OK: {msg}")


def main():
    words = load_words()
    g = Game(game_id="test1", chat_id=123, host_id=1, team_size_mode=4)

    # --- تست لابی ---
    g.join_slot(1, "Ali", Team.RED, Role.SPYMASTER, slot=0)
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)
    assert_true(not g.is_ready_to_start(), "تیم آبی خالیه پس نباید آماده‌ی شروع باشه")

    g.join_slot(3, "Sara", Team.BLUE, Role.SPYMASTER, slot=0)
    g.join_slot(4, "Neda", Team.BLUE, Role.OPERATIVE, slot=0)
    assert_true(g.is_ready_to_start(), "حالا هر دو تیم پر شدن، باید آماده باشه")

    # تست پر بودن اسلات در حالت ۴ نفره (فقط ۱ مامور مجاز، یعنی فقط اسلات ۰)
    try:
        g.join_slot(5, "Extra", Team.RED, Role.OPERATIVE, slot=1)
        assert_true(False, "نباید بذاره یه مامور دوم بشینه توی حالت ۴ نفره (اسلات ۱ نباید وجود داشته باشه)")
    except GameError:
        print("✅ OK: جلوی نشستن مامور اضافه در حالت ۴نفره گرفته شد")

    # تست اینکه کلیک روی اسلات اشغال‌شده توسط یکی دیگه رد بشه
    try:
        g.join_slot(6, "AnotherAli", Team.RED, Role.SPYMASTER, slot=0)
        assert_true(False, "نباید بذاره یکی دیگه روی اسلات اشغال‌شده بشینه")
    except GameError:
        print("✅ OK: جلوی نشستن روی اسلات اشغال‌شده گرفته شد")

    # تست toggle: کلیک خودِ آدم روی اسلات خودش -> باید خارج بشه
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)
    assert_true(2 not in g.players, "با کلیک مجدد رضا روی اسلات خودش، باید از لابی خارج بشه")
    # برش‌گردون برای ادامه‌ی تست
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)

    # تست تغییر نفرات به ۶ نفره و اینکه حالا جا باز میشه
    g.cycle_team_size()
    assert_true(g.team_size_mode == 6, "بعد از یه‌بار تغییر نفرات باید ۶نفره بشه")
    g.join_slot(5, "Extra", Team.RED, Role.OPERATIVE, slot=1)
    assert_true(len(g.players) == 5, "حالا باید بازیکن پنجم هم اضافه شده باشه")

    # برگردون به ۴ نفره -> باید بازیکن اسلات ۱ (که در ۴نفره وجود نداره) حذف بشه
    g.cycle_team_size()  # -> 8
    g.cycle_team_size()  # -> 4
    assert_true(g.team_size_mode == 4, "باید برگرده به ۴نفره")
    assert_true(5 not in g.players, "بازیکنی که تو اسلات ۱ بود باید با کوچیک‌شدن ظرفیت حذف بشه")

    # --- تست شروع بازی ---
    g.start_game(words)
    assert_true(len(g.board) == 25, "باید ۲۵ کارت روی برد باشه")
    assert_true(g.status == GameStatus.AWAITING_CLUE, "بعد شروع، باید منتظر تعیین تعداد سرنخ باشه")
    reds = sum(1 for c in g.board if c.color.value == "red")
    blues = sum(1 for c in g.board if c.color.value == "blue")
    neutrals = sum(1 for c in g.board if c.color.value == "neutral")
    assassins = sum(1 for c in g.board if c.color.value == "assassin")
    assert_true(reds + blues == 17, "مجموع قرمز و آبی باید ۱۷ باشه (۹+۸)")
    assert_true(neutrals == 7, "باید ۷ کارت خنثی باشه")
    assert_true(assassins == 1, "باید دقیقاً ۱ کارت قاتل باشه")

    # --- تست تعیین تعداد سرنخ و اتمام حدس زودهنگام ---
    g.set_clue_count(2)
    assert_true(g.status == GameStatus.GUESSING, "بعد تعیین سرنخ باید بره تو فاز حدس")
    try:
        g.end_guessing()
        assert_true(False, "نباید بذاره قبل از ۲ حدس درست، اتمام حدس بزنه")
    except GameError:
        print("✅ OK: اتمام حدس زودهنگام درست بلاک شد")

    # پیدا کردن یه خانه هم‌رنگ تیم جاری برای حدس درست
    current_color = g.current_turn.value
    idx_correct = next(i for i, c in enumerate(g.board) if c.color.value == current_color and not c.revealed)
    result = g.guess(idx_correct, "تستی")
    assert_true(result.value == current_color, "حدس درست باید رنگ خودی برگردونه")
    assert_true(g.status == GameStatus.GUESSING, "بعد حدس درست هنوز باید تو فاز حدس بمونیم")
    assert_true(g.correct_guesses_this_turn == 1, "شمارنده‌ی حدس درست باید ۱ بشه")

    # هنوز به ۲ نرسیدیم، اتمام حدس باید بلاک باشه
    try:
        g.end_guessing()
        assert_true(False, "با فقط ۱ حدس درست از ۲ لازم، نباید اتمام حدس مجاز باشه")
    except GameError:
        print("✅ OK: با ۱ از ۲ هنوز بلاکه")

    # حدس دوم درست
    idx_correct2 = next(i for i, c in enumerate(g.board) if c.color.value == current_color and not c.revealed)
    g.guess(idx_correct2, "تستی")
    assert_true(g.correct_guesses_this_turn == 2, "باید به ۲ برسه")
    assert_true(g.can_end_guessing(), "حالا باید اتمام حدس مجاز باشه")

    prev_turn = g.current_turn
    g.end_guessing()
    assert_true(g.current_turn != prev_turn, "با زدن اتمام حدس، نوبت باید عوض بشه")
    assert_true(g.status == GameStatus.AWAITING_CLUE, "نوبت جدید باید منتظر سرنخ جدید باشه")

    # --- تست حدس اشتباه -> تعویض خودکار نوبت ---
    g.set_clue_count(3)
    prev_turn = g.current_turn
    other_color = "blue" if prev_turn.value == "red" else "red"
    idx_wrong = next(i for i, c in enumerate(g.board) if c.color.value == other_color and not c.revealed)
    g.guess(idx_wrong, "تستی")
    assert_true(g.current_turn != prev_turn, "حدس اشتباه باید خودکار نوبت رو عوض کنه")

    # --- تست پایان دست دستی ---
    g.set_clue_count(1)
    prev_turn = g.current_turn
    g.end_turn()
    assert_true(g.current_turn != prev_turn, "دکمه‌ی پایان دست باید بدون قید و شرط نوبت رو عوض کنه")

    # --- تست سریالایز/دیسریالایز (برای SQLite) ---
    as_json = g.to_json()
    g2 = Game.from_json(as_json)
    assert_true(g2.board[0].word == g.board[0].word, "بعد از سریالایز/بازسازی، برد باید یکی باشه")
    assert_true(g2.current_turn == g.current_turn, "نوبت باید بعد از بازسازی حفظ بشه")

    print("\n🎉 همه‌ی تست‌ها با موفقیت رد شدن.")


def test_guess_log_and_round():
    words = load_words()
    g = Game(game_id="test2", chat_id=1, host_id=1, team_size_mode=4)
    g.join_slot(1, "Ali", Team.RED, Role.SPYMASTER, slot=0)
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)
    g.join_slot(3, "Sara", Team.BLUE, Role.SPYMASTER, slot=0)
    g.join_slot(4, "Neda", Team.BLUE, Role.OPERATIVE, slot=0)
    g.start_game(words)

    assert_true(g.round_number == 1, "راند اول باید ۱ باشه")

    g.set_clue_count(1)
    current_color = g.current_turn.value
    idx = next(i for i, c in enumerate(g.board) if c.color.value == current_color and not c.revealed)
    guesser_name = "Reza" if g.current_turn == Team.RED else "Neda"
    g.guess(idx, guesser_name)

    log = g.guess_log[current_color]
    assert_true(len(log) == 1, "باید یه ردیف تو لاگ همون تیم اضافه شده باشه")
    assert_true(log[0][0] == guesser_name, "اسم پلیر باید درست ثبت شده باشه")
    assert_true(log[0][1] == g.board[idx].word, "کلمه‌ی حدس‌زده‌شده باید درست ثبت شده باشه")
    assert_true(g.board[idx].guessed_by == g.current_turn, "guessed_by باید تیم فعلی باشه")

    prev_round = g.round_number
    g.end_turn()
    assert_true(g.round_number == prev_round + 1, "با تعویض نوبت، شماره‌ی راند باید یکی زیاد بشه")

    g2 = Game.from_json(g.to_json())
    assert_true(g2.round_number == g.round_number, "راند باید بعد از بازسازی حفظ بشه")
    assert_true(g2.guess_log == g.guess_log, "لاگ حدس باید بعد از بازسازی حفظ بشه")

    print("\n🎉 تست‌های guess_log و round_number هم رد شدن.")


if __name__ == "__main__":
    main()
    test_guess_log_and_round()
