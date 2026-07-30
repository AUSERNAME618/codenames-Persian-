"""
تستِ رفعِ باگِ «پریدنِ حدس‌ها» / «اپدیت‌نشدنِ پنل» که در واقع یه race condition بود:
دو تا اکشنِ هم‌زمان روی یه بازی، هرکدوم حالتِ اولیه‌ی یکسان رو می‌خوندن و آخری که
save می‌کرد، تغییرِ اون یکی رو کامل پاک می‌کرد (lost update).

این تست دقیقاً همون سناریو رو با/بدونِ قفل شبیه‌سازی می‌کنه تا ثابت کنه game/locks.py
واقعاً مشکل رو حل می‌کنه.
"""
import asyncio
import sys

from game.locks import get_game_lock


class FakeGame:
    """یه نسخه‌ی خیلی ساده‌شده از الگوی load->تغییر->save برای شبیه‌سازیِ race."""

    def __init__(self):
        self.guesses: list[str] = []


class FakeDB:
    def __init__(self):
        self.stored = FakeGame()

    async def load(self) -> FakeGame:
        await asyncio.sleep(0.05)  # شبیه‌سازیِ تأخیرِ شبکه/DB
        # یه کپیِ عمیق برمی‌گردونیم (دقیقاً مثلِ اینکه از JSON دیتابیس بازسازی بشه)
        g = FakeGame()
        g.guesses = list(self.stored.guesses)
        return g

    async def save(self, g: FakeGame) -> None:
        await asyncio.sleep(0.05)  # شبیه‌سازیِ تأخیرِ شبکه/DB
        self.stored = g


def check(cond, msg):
    status = "✅ OK" if cond else "❌ FAIL"
    print(f"{status}: {msg}")
    if not cond:
        sys.exit(1)


async def do_guess_without_lock(db: FakeDB, word: str) -> None:
    g = await db.load()
    g.guesses.append(word)
    await db.save(g)


async def do_guess_with_lock(db: FakeDB, word: str) -> None:
    async with get_game_lock("race-test-game"):
        g = await db.load()
        g.guesses.append(word)
        await db.save(g)


async def main() -> None:
    # ---------- بدونِ قفل: باید یه حدس گم بشه (دقیقاً باگِ گزارش‌شده) ----------
    db1 = FakeDB()
    await asyncio.gather(
        do_guess_without_lock(db1, "کلمه_الف"),
        do_guess_without_lock(db1, "کلمه_ب"),
    )
    lost_happened = len(db1.stored.guesses) < 2
    check(
        lost_happened,
        "بدونِ قفل: باید دقیقاً همون باگِ گزارش‌شده (گم‌شدنِ یکی از حدس‌ها) تکرار بشه "
        f"(نتیجه: {db1.stored.guesses})",
    )

    # ---------- با قفل: هر دو حدس باید سالم بمونن ----------
    db2 = FakeDB()
    await asyncio.gather(
        do_guess_with_lock(db2, "کلمه_الف"),
        do_guess_with_lock(db2, "کلمه_ب"),
    )
    check(
        len(db2.stored.guesses) == 2 and set(db2.stored.guesses) == {"کلمه_الف", "کلمه_ب"},
        f"با قفل: هر دو حدس باید سالم ذخیره بشن، نه گم بشن (نتیجه: {db2.stored.guesses})",
    )

    # ---------- تستِ تکراری (چندبار، برای اطمینان از پایداری) ----------
    for i in range(10):
        db = FakeDB()
        await asyncio.gather(*(do_guess_with_lock(db, f"g{i}_{j}") for j in range(5)))
        check(len(db.stored.guesses) == 5, f"تکرارِ {i}: هر ۵ اکشنِ هم‌زمان باید سالم ذخیره بشن")

    print("\n🎉 تستِ رفعِ race condition رد شد - قفل واقعاً از lost update جلوگیری می‌کنه.")


async def test_coalesced_sync() -> None:
    from game.locks import coalesced_sync

    run_count = [0]
    max_concurrent = [0]
    current_concurrent = [0]

    async def fake_sync():
        current_concurrent[0] += 1
        max_concurrent[0] = max(max_concurrent[0], current_concurrent[0])
        run_count[0] += 1
        await asyncio.sleep(0.05)
        current_concurrent[0] -= 1

    # ۵ درخواستِ تقریباً هم‌زمان روی یه بازی - نباید بیش از یکی هم‌زمان اجرا بشه
    await asyncio.gather(*(coalesced_sync("coalesce-test", fake_sync) for _ in range(5)))

    check(max_concurrent[0] == 1, f"coalesced_sync: نباید بیش از ۱ اجرای هم‌زمان داشته باشیم (شد {max_concurrent[0]})")
    check(1 <= run_count[0] <= 5, f"coalesced_sync: باید حداقل یه‌بار و حداکثر ۵بار (یکی‌به‌یکی) اجرا بشه (شد {run_count[0]})")

    print(f"\n🎉 تستِ coalesced_sync رد شد (اجرای هم‌زمانِ بیشینه={max_concurrent[0]}, تعدادِ اجرا={run_count[0]}).")


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(test_coalesced_sync())
