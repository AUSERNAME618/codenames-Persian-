"""
ساختِ برد ۲۵تایی بسته به سطحِ دشواری.

سه حالت:
- hard:   کاملاً رندوم (رفتارِ قبلی و بدون تغییر، بدونِ خوشه)
- medium: چندتا خوشه‌ی کم‌ربط (نه خیلی مشابه) به هر تیم داده می‌شه، بدونِ توجه به
          این‌که کلماتِ خوشه با کلماتِ تیمِ حریف/خنثی/قاتل هم‌موضوع باشن یا نه
- easy:   چندتا خوشه‌ی واضح‌ترِ به هر تیم داده می‌شه + تضمین می‌شه که کلماتِ نزدیک‌به‌اون
          خوشه (avoid) جای دیگه‌ای روی برد (تیمِ حریف/خنثی/قاتل) ظاهر نشن، تا کسی
          گیج نشه و مسیرِ اشتباه نره

هر خوشه: {"difficulty": "easy"|"medium", "words": [...], "avoid": [...]}
avoid فقط برای easy پر می‌شه؛ برای medium همیشه خالیه (نیازی به رعایتش نیست).

این ماژول کاملاً مستقل و تست‌پذیره؛ فقط لیستِ کلمه + رنگ برمی‌گردونه، هیچ وابستگی‌ای
به aiogram/تلگرام نداره.
"""
from __future__ import annotations

import random
from typing import Optional


def _pick_clusters_for_slots(
    pool: list[dict],
    target_count: int,
    used_words: set[str],
    used_avoid: set[str],
    rng: random.Random,
    respect_avoid: bool,
) -> list[str]:
    """
    از pool (خوشه‌های یه سطح‌ِ دشواری) اونقدر خوشه انتخاب می‌کنه که مجموعِ کلماتش از
    target_count بیشتر نشه. هر خوشه فقط وقتی انتخاب می‌شه که:
    - هیچ‌کدوم از کلماتش قبلاً جای دیگه‌ای استفاده نشده باشه
    - (اگه respect_avoid=True) هیچ‌کدوم از کلماتش جزوِ avoid یه خوشه‌ی دیگه که قبلاً
      انتخاب شده نباشه، و برعکس: کلماتِ avoid این خوشه با کلماتِ استفاده‌شده تداخل نداشته باشه
    used_words/used_avoid درجا آپدیت می‌شن (side effect عمدیه، برای سادگیِ فراخوانی).
    """
    shuffled = pool.copy()
    rng.shuffle(shuffled)
    chosen: list[str] = []

    for cluster in shuffled:
        words = cluster["words"]
        avoid = set(cluster.get("avoid", [])) if respect_avoid else set()

        if len(chosen) + len(words) > target_count:
            continue
        if any(w in used_words for w in words):
            continue
        if respect_avoid:
            if any(w in used_avoid for w in words):
                continue
            if any(w in avoid for w in used_words):
                continue

        chosen.extend(words)
        used_words.update(words)
        used_avoid.update(avoid)

        if len(chosen) >= target_count:
            break

    return chosen


def _fill_random(
    word_pool: list[str],
    count: int,
    forbidden: set[str],
    rng: random.Random,
) -> list[str]:
    """count کلمه‌ی رندوم از word_pool انتخاب می‌کنه، به استثنای forbidden."""
    available = [w for w in word_pool if w not in forbidden]
    if len(available) < count:
        # fallback خیلی بعیده پیش بیاد (فقط اگه دیتابیس خیلی کوچیک باشه)، ولی برای
        # امنیت: اگه کم آوردیم، محدودیتِ forbidden رو نادیده می‌گیریم
        available = [w for w in word_pool if w not in set()]
    return rng.sample(available, count)


def build_board(
    word_pool: list[str],
    clusters: list[dict],
    n_starting: int,
    n_other: int,
    n_neutral: int,
    n_assassin: int,
    difficulty: str = "hard",
    cluster_coverage: float = 0.7,
    rng: Optional[random.Random] = None,
) -> list[str]:
    """
    خروجی: لیستی از n_starting+n_other+n_neutral+n_assassin کلمه، به همین ترتیب
    (بخشِ اول برای تیمِ شروع‌کننده، بعد تیمِ دیگه، بعد خنثی، بعد قاتل). ترتیبِ نهاییِ
    جای‌گذاری روی برد (shuffle) رو خودِ فراخوان (game/state.py) انجام می‌ده.

    difficulty:
    - "hard": بدونِ خوشه، کاملاً رندوم
    - "medium"/"easy": با خوشه‌های همون سطح
    """
    rng = rng or random
    total = n_starting + n_other + n_neutral + n_assassin

    if difficulty == "hard" or not clusters:
        return rng.sample(word_pool, total)

    pool_for_level = [c for c in clusters if c.get("difficulty") == difficulty]
    respect_avoid = difficulty == "easy"

    used_words: set[str] = set()
    used_avoid: set[str] = set()

    starting_target = round(n_starting * cluster_coverage)
    other_target = round(n_other * cluster_coverage)

    starting_cluster_words = _pick_clusters_for_slots(
        pool_for_level, starting_target, used_words, used_avoid, rng, respect_avoid
    )
    other_cluster_words = _pick_clusters_for_slots(
        pool_for_level, other_target, used_words, used_avoid, rng, respect_avoid
    )

    starting_remaining = n_starting - len(starting_cluster_words)
    other_remaining = n_other - len(other_cluster_words)
    filler_needed = starting_remaining + other_remaining + n_neutral + n_assassin

    forbidden = used_words | (used_avoid if respect_avoid else set())
    filler_words = _fill_random(word_pool, filler_needed, forbidden, rng)

    # تقسیمِ filler_words بینِ بخش‌های مختلف
    idx = 0
    starting_filler = filler_words[idx: idx + starting_remaining]
    idx += starting_remaining
    other_filler = filler_words[idx: idx + other_remaining]
    idx += other_remaining
    neutral_words = filler_words[idx: idx + n_neutral]
    idx += n_neutral
    assassin_words = filler_words[idx: idx + n_assassin]

    starting_words = starting_cluster_words + starting_filler
    other_words = other_cluster_words + other_filler

    # هر بخش رو خودش هم به‌هم بریزیم که ترتیبِ کلمات همیشه یکسان نباشه
    rng.shuffle(starting_words)
    rng.shuffle(other_words)

    return starting_words + other_words + neutral_words + assassin_words
