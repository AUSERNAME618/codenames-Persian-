"""
تستِ عملیِ رفعِ باگِ «کندی/فریزِ ربات حین بازیِ فعال».
علتِ اصلیِ باگ: رندرِ Pillow (CPU-bound) مستقیم داخلِ تابعِ async صدا زده می‌شد و کلِ
event loop رو حین رندر می‌بست - یعنی هیچ بازیِ دیگه‌ای (توی هیچ گروهِ دیگه‌ای) هم
نمی‌تونست پردازش بشه.

این تست ثابت می‌کنه که با استفاده از asyncio.to_thread (که الان توی
handlers/game_flow.py استفاده می‌شه)، یه «ضربان‌سنج» async می‌تونه آزادانه و مرتب
حین انجام‌شدنِ رندر هم تیک بزنه - یعنی event loop واقعاً بلاک نمی‌شه.
"""
import asyncio
import json
import sys
import time

from imaging.board_renderer import render_board


def load_words():
    with open("data/words_fa.json", encoding="utf-8") as f:
        return json.load(f)


def check(cond, msg):
    status = "✅ OK" if cond else "❌ FAIL"
    print(f"{status}: {msg}")
    if not cond:
        sys.exit(1)


def _render_sync(words):
    cards = [{"word": w, "state": "unrevealed"} for w in words[:25]]
    return render_board(
        cards=cards, current_turn="blue", round_number=1,
        red_cards_remaining=9, blue_cards_remaining=8,
        red_operatives=["مریم"], blue_operatives=["علی"],
        red_spymaster="نگار", blue_spymaster="حسین",
        red_guess_log=[], blue_guess_log=[], clue_word=None, clue_number=None,
    )


async def _heartbeat(counter: list, stop_event: asyncio.Event):
    while not stop_event.is_set():
        counter[0] += 1
        await asyncio.sleep(0.01)  # هر ۱۰ میلی‌ثانیه یه‌بار تیک بزن


async def main():
    words = load_words()

    # یه رندر اول (gرم‌کردنِ کش‌ها) - وگرنه رندرِ اول به‌خاطرِ کشِ خالی کندتره و
    # نمی‌ذاره مقایسه‌ی منصفانه‌ای انجام بشه
    _render_sync(words)

    counter = [0]
    stop_event = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat(counter, stop_event))

    t0 = time.time()
    # دقیقاً همون الگویی که الان توی game_flow.py استفاده می‌شه: to_thread
    await asyncio.to_thread(_render_sync, words)
    render_duration = time.time() - t0

    stop_event.set()
    await hb_task

    expected_min_ticks = max(1, int(render_duration / 0.01 * 0.5))  # حداقل نصفِ تیک‌های انتظاری
    print(f"مدتِ رندر: {render_duration:.3f}s | تعدادِ تیک‌های ضربان‌سنج حین رندر: {counter[0]}")
    check(
        counter[0] >= expected_min_ticks,
        f"ضربان‌سنجِ async باید حداقل {expected_min_ticks} بار حین رندر تیک بزنه "
        f"(یعنی event loop بلاک نشده)، ولی فقط {counter[0]} بار تیک زد",
    )

    print("\n🎉 تستِ عدمِ بلاک‌شدنِ event loop حین رندر رد شد.")


if __name__ == "__main__":
    asyncio.run(main())
