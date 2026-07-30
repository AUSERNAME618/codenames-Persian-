import json
import random
import sys

from game.board_builder import build_board

N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN = 9, 8, 7, 1
TOTAL = N_STARTING + N_OTHER + N_NEUTRAL + N_ASSASSIN


def check(condition, label):
    status = "✅ OK" if condition else "❌ FAIL"
    print(f"{status}: {label}")
    if not condition:
        raise SystemExit(1)


def load_real_data():
    with open("data/words_fa.json", encoding="utf-8") as f:
        words = json.load(f)
    with open("data/word_clusters.json", encoding="utf-8") as f:
        clusters = json.load(f)
    return words, clusters


def main():
    words, clusters = load_real_data()

    # ---------- حالت hard ----------
    for seed in range(20):
        rng = random.Random(seed)
        board = build_board(words, clusters, N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                             difficulty="hard", rng=rng)
        check(len(board) == TOTAL, f"hard seed={seed}: تعدادِ کل باید {TOTAL} باشه")
        check(len(set(board)) == TOTAL, f"hard seed={seed}: نباید کلمه‌ی تکراری باشه")

    # ---------- حالت medium ----------
    for seed in range(20):
        rng = random.Random(seed)
        board = build_board(words, clusters, N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                             difficulty="medium", rng=rng)
        check(len(board) == TOTAL, f"medium seed={seed}: تعدادِ کل باید {TOTAL} باشه")
        check(len(set(board)) == TOTAL, f"medium seed={seed}: نباید کلمه‌ی تکراری باشه")

    # ---------- حالت easy ----------
    easy_clusters = [c for c in clusters if c["difficulty"] == "easy"]
    for seed in range(30):
        rng = random.Random(seed)
        board = build_board(words, clusters, N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                             difficulty="easy", rng=rng)
        check(len(board) == TOTAL, f"easy seed={seed}: تعدادِ کل باید {TOTAL} باشه")
        check(len(set(board)) == TOTAL, f"easy seed={seed}: نباید کلمه‌ی تکراری باشه")

        board_set = set(board)
        # قانونِ اصلیِ easy: برای هر خوشه‌ای که کاملاً روی برد هست، هیچ‌کدوم از
        # کلماتِ avoid‌ش نباید جای دیگه‌ای (هرجایی) روی همون برد ظاهر بشه
        for cluster in easy_clusters:
            cwords = set(cluster["words"])
            if cwords.issubset(board_set):
                avoid_leak = cwords_avoid = set(cluster.get("avoid", [])) & board_set
                check(
                    not avoid_leak,
                    f"easy seed={seed}: خوشه‌ی {cluster['words']} روی برده ولی "
                    f"کلماتِ avoid‌ش {avoid_leak} هم روش پیدا شدن (نباید باشن)"
                )

    # ---------- خوشه‌ها واقعاً استفاده می‌شن (نه صرفاً fallback به رندوم) ----------
    used_any_cluster = False
    for seed in range(30):
        rng = random.Random(seed)
        board = build_board(words, clusters, N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                             difficulty="easy", rng=rng)
        board_set = set(board)
        for cluster in easy_clusters:
            if set(cluster["words"]).issubset(board_set):
                used_any_cluster = True
                break
        if used_any_cluster:
            break
    check(used_any_cluster, "easy: حداقل توی یکی از ۳۰ تلاش، یه خوشه‌ی کامل باید روی برد ظاهر بشه")

    # ---------- edge case: کلاسترها خالی باشن نباید کرش کنه ----------
    rng = random.Random(1)
    board = build_board(words, [], N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                         difficulty="easy", rng=rng)
    check(len(board) == TOTAL and len(set(board)) == TOTAL,
          "easy با لیستِ خوشه‌ی خالی: باید بدونِ کرش به رندومِ کامل fallback کنه")

    # ---------- حالتِ hard نباید هیچ اثری از خوشه‌ها داشته باشه ----------
    # با wordهای خیلی کوچیک و یه خوشه‌ی جعلی، مطمئن می‌شیم حالتِ hard اصلاً
    # وارد منطقِ خوشه‌بندی نمی‌شه (نتیجه باید مستقل از وجود/عدم‌وجودِ clusters باشه)
    fake_clusters = [{"difficulty": "easy", "words": ["الف", "ب", "پ"], "avoid": ["ت"]}]
    rng1 = random.Random(42)
    board_with = build_board(words, fake_clusters, N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                              difficulty="hard", rng=rng1)
    rng2 = random.Random(42)
    board_without = build_board(words, [], N_STARTING, N_OTHER, N_NEUTRAL, N_ASSASSIN,
                                 difficulty="hard", rng=rng2)
    check(board_with == board_without,
          "hard: نتیجه باید کاملاً مستقل از وجودِ کلاسترها باشه (خروجی با/بدونِ کلاستر یکسان)")

    print("\n🎉 همه‌ی تست‌های board_builder رد شدن.")


if __name__ == "__main__":
    main()
