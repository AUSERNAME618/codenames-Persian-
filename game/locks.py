"""
قفلِ per-game برای جلوگیری از race condition.

مشکل: load_game -> تغییر -> save_game هیچ تراکنش/نسخه‌بندی‌ای نداره. اگه دو بازیکن
تقریباً هم‌زمان دکمه بزنن، هر دو حالتِ اولیه‌ی یکسان رو می‌خونن، هرکدوم جدا تغییرش
می‌دن، و هرکدوم که save_game رو دیرتر صدا بزنه، تغییرِ اون یکی رو کامل بدونِ اطلاع
پاک می‌کنه (lost update). این باعثِ «پریدنِ» حدس‌ها و اپدیت‌نشدنِ ظاهریِ پنل می‌شه.

راه‌حل: یه asyncio.Lock مخصوصِ هر game_id، که کل چرخه‌ی load->تغییر->save->sync
(نه فقط خودِ save) رو دربر می‌گیره. درخواست‌های هم‌زمان روی *همون* بازی صف می‌شن
(نه هم‌زمان اجرا می‌شن)، ولی بازی‌های دیگه (چت‌های دیگه) کاملاً موازی و بدون تأخیر
پردازش می‌شن - چون هرکدوم قفلِ جدا دارن.
"""
from __future__ import annotations

import asyncio

_locks: dict[str, asyncio.Lock] = {}


def get_game_lock(game_id: str) -> asyncio.Lock:
    lock = _locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[game_id] = lock
    return lock


def drop_game_lock(game_id: str) -> None:
    """وقتی بازی حذف/تموم می‌شه، قفلش رو هم پاک می‌کنیم که دیکشنری بی‌نهایت بزرگ نشه."""
    _locks.pop(game_id, None)
    _sync_in_progress.pop(game_id, None)
    _sync_pending.pop(game_id, None)


# --- Coalescing برای sync (رندر/ارسالِ عکس) ---
# اگه چندتا اکشنِ پشتِ‌سرِهم روی یه بازی، هرکدوم بخوان جدا عکس بفرستن، دو/سه‌تا عکسِ
# تقریباً هم‌زمان و اضافه ارسال می‌شه (اسپم، و هم مصرفِ بی‌موردِ منابع). این مکانیزم
# تضمین می‌کنه هیچ‌وقت بیش از یه sync هم‌زمان روی یه بازی در حالِ اجرا نباشه: اگه یکی
# در حالِ اجراست، درخواستِ جدید فقط یه پرچمِ "دوباره لازمه" ست می‌کنه (نه اینکه صفِ
# جدید بسازه)؛ همون sync در حالِ اجرا، بعدِ تمومِ کارش، اگه پرچم ست شده بود، *یه‌بار
# دیگه* (نه به تعداد، فقط یه‌بار) با جدیدترین حالت اجرا می‌شه.
_sync_in_progress: dict[str, bool] = {}
_sync_pending: dict[str, bool] = {}


async def coalesced_sync(game_id: str, sync_fn) -> None:
    """
    sync_fn: یه تابعِ async بدونِ آرگومان که واقعاً رندر/ارسال رو انجام می‌ده.
    اگه sync دیگه‌ای همین الان داره روی همین game_id اجرا می‌شه، این فراخوانی فقط
    صبر می‌کنه تا اون یکی تموم بشه و به‌جاش یه اجرای اضافه (با جدیدترین حالت) انجام
    بشه - نه اینکه خودش هم موازی اجرا بشه.
    """
    if _sync_in_progress.get(game_id):
        _sync_pending[game_id] = True
        return

    _sync_in_progress[game_id] = True
    try:
        await sync_fn()
        while _sync_pending.pop(game_id, False):
            await sync_fn()
    finally:
        _sync_in_progress[game_id] = False
