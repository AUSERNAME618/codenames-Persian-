import os

# توکن ربات را از متغیر محیطی بخوان (هرگز مستقیم در کد ننویس)
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

# رشته‌ی اتصال Postgres (از Neon کپی می‌شه، چیزی شبیه:
# postgresql://user:password@host/dbname?sslmode=require)
DATABASE_URL = os.getenv("DATABASE_URL", "PUT_YOUR_NEON_CONNECTION_STRING_HERE")

# مسیر فایل لیست کلمات (JSON آرایه‌ای از رشته‌های فارسی)
WORDS_PATH = os.getenv("WORDS_PATH", "data/words_fa.json")

# مسیر فایلِ خوشه‌های کلمه‌ای (برای گیم‌مودِ آسون/متوسط)
WORD_CLUSTERS_PATH = os.getenv("WORD_CLUSTERS_PATH", "data/word_clusters.json")

# لیستِ عکس‌های بنرِ لابی - هر بازیِ جدید، به‌ترتیب (نه رندوم) یکی از این‌ها رو
# استفاده می‌کنه. هر تعداد عکس می‌تونی بذاری (فقط ۱ تا، یا بیشتر). اگه فایلی وجود
# نداشته باشه، خودکار نادیده گرفته می‌شه؛ اگه هیچ‌کدوم نبودن، fallback به متنِ ساده.
LOBBY_BANNER_PATHS = [
    p.strip()
    for p in os.getenv(
        "LOBBY_BANNER_PATHS",
        "assets/images/lobby_banner_1.jpg,assets/images/lobby_banner_2.jpg,assets/images/lobby_banner_3.jpg",
    ).split(",")
    if p.strip()
]

# ترتیب چرخشی سطح دشواری با دکمه‌ی «تغییر سطح»
DIFFICULTY_CYCLE = ["hard", "medium", "easy"]
DIFFICULTY_LABELS_FA = {"hard": "سخت", "medium": "متوسط", "easy": "آسون"}

# چند درصد از کارت‌های هر تیم سعی می‌شه از خوشه‌ها پر بشه (بقیه رندومِ خالص)
CLUSTER_COVERAGE = 0.7

# تعداد کلمات روی صفحه (همیشه ۵×۵ = ۲۵)
BOARD_SIZE = 25

# تنظیمات حالت‌های مختلف تعداد نفرات
# هر حالت: چند مامور و چند جاسوس در هر تیم مجاز است
TEAM_SIZE_MODES = {
    4: {"operatives_per_team": 1, "spymasters_per_team": 1},
    6: {"operatives_per_team": 2, "spymasters_per_team": 1},
    8: {"operatives_per_team": 3, "spymasters_per_team": 1},
}

# ترتیب چرخشی حالت‌ها با دکمه‌ی «تغییر نفرات»
TEAM_SIZE_CYCLE = [4, 6, 8]

# تقسیم رنگ ۲۵ خانه بر اساس تیم شروع‌کننده
# تیم شروع‌کننده ۹ کارت، تیم دیگر ۸ کارت، ۷ خنثی، ۱ قاتل
CARDS_PER_STARTING_TEAM = 9
CARDS_PER_OTHER_TEAM = 8
CARDS_NEUTRAL = 7
CARDS_ASSASSIN = 1

# هر چند ثانیه callback query باید answer شود حتی اگر کاری انجام نشد
# (جلوگیری از حالت loading روی دکمه در گوشی کاربر)
