"""
رنگ‌ها و اندازه‌های ثابت برای ساخت تصویر پنل بازی.
همه‌ی رنگ‌های اصلی طبق کدهای دقیقِ داده‌شده توسط کاربر؛ برای هرکدوم یه تُنِ
روشن‌تر/تیره‌تر برای گرادیانِ ملایم به‌صورت خودکار محاسبه شده تا رنگِ یکدست و
تخت به نظر نرسه.
"""

# --- رنگ‌های کارت (گرادیان مورب: روشن -> تیره/اصلی) ---
CARD_CREAM = ("#ecd7b5", "#E9D0A9")               # فاش‌نشده (نشونِ مامورها قبل از لو رفتن)
CARD_NEUTRAL_REVEALED = ("#c5ae81", "#BB9F69")    # خنثیِ فاش‌شده
CARD_RED = ("#955151", "#640000")                 # فاش‌شده - تیم قرمز
CARD_BLUE = ("#526282", "#102552")                # فاش‌شده - تیم آبی
CARD_ASSASSIN = ("#343434", "#020202")            # فاش‌شده - قاتل

CARD_BORDER_CREAM = "#baa687"
CARD_BORDER_NEUTRAL_REVEALED = "#957f54"
CARD_BORDER_RED = "#480000"
CARD_BORDER_BLUE = "#0b1a3b"
CARD_BORDER_ASSASSIN = "#000000"

TEXT_DARK = "#3a2f22"       # متن روی کارت‌های کرم / خنثیِ فاش‌شده
TEXT_WHITE = "#ffffff"      # متن روی کارت‌های رنگی و قاتل

# --- رنگ‌های پنل تیم (نسخه‌ی تکی = دقیقاً همون رنگی که کاربر داد، برای متن/نشونه‌ها) ---
PANEL_BLUE = "#191971"
PANEL_RED = "#8B1221"
# --- نسخه‌ی گرادیان (روشن -> تیره/اصلی) برای پس‌زمینه‌ی خودِ پنل، تا تخت به نظر نرسه ---
PANEL_BLUE_GRADIENT = ("#2c2c9e", "#191971")
PANEL_RED_GRADIENT = ("#b93049", "#8B1221")

# --- پس‌زمینه‌ی کل تصویر (بسته به نوبت) ---
BG_BLUE_TURN = ("#1560BD", "#0e4384")
BG_RED_TURN = ("#CB3534", "#8e2524")
BG_GRAY_ASSASSIN = ("#454545", "#171717")   # هم برای پس‌زمینه‌ی باختِ کارت قاتل، هم عکسِ خصوصیِ جاسوس

# لاگ حدس: سفید با حاشیه‌ی مشکی نازک، تا روی هر سه پس‌زمینه (آبی/قرمز/طوسی) خوانا بمونه
LOG_TEXT_COLOR = "#ffffff"
LOG_STROKE_COLOR = "#000000"

WHITE = "#ffffff"
BLACK = "#000000"

# --- فونت‌ها ---
FONT_DIR = "assets/fonts"
FONT_BLACK = f"{FONT_DIR}/Pofak-_Black.ttf"
FONT_EXTRABOLD = f"{FONT_DIR}/Pofak-ExtraBold.ttf"
FONT_DEMIBOLD = f"{FONT_DIR}/Pofak-DemiBold.ttf"
FONT_MEDIUM = f"{FONT_DIR}/Pofak-Medium.ttf"
FONT_REGULAR = f"{FONT_DIR}/Pofak-_Regular.ttf"
FONT_LIGHT = f"{FONT_DIR}/Pofak-Light.ttf"

# --- اندازه‌های چیدمان (پیکسل) - بزرگ، برای پرکردن حداکثر فضای تصویر ---
CANVAS_W = 2192
CANVAS_H = 1469

GRID_COLS = 5
GRID_ROWS = 5
CARD_W = 260
CARD_H = 165
CARD_GAP = 20
CARD_RADIUS = 28

PANEL_W = 380
PANEL_RADIUS = 36

MARGIN_TOP = 150   # فضای بالای تصویر برای شماره‌ی راند
MARGIN_BOTTOM = 170  # فضای پایین برای مربع عدد + مستطیل کلمه‌ی سرنخ
