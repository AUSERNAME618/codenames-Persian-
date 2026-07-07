import os

# توکن ربات را از متغیر محیطی بخوان (هرگز مستقیم در کد ننویس)
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

# رشته‌ی اتصال Postgres (از Neon کپی می‌شه، چیزی شبیه:
# postgresql://user:password@host/dbname?sslmode=require)
DATABASE_URL = os.getenv("DATABASE_URL", "PUT_YOUR_NEON_CONNECTION_STRING_HERE")

# مسیر فایل لیست کلمات (JSON آرایه‌ای از رشته‌های فارسی)
WORDS_PATH = os.getenv("WORDS_PATH", "data/words_fa.json")

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
