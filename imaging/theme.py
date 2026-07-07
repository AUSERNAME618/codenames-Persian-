"""
رنگ‌ها و اندازه‌های ثابت برای ساخت تصویر پنل بازی.
رنگ‌ها از روی نمونه‌عکس‌های خودِ کاربر نمونه‌برداری شدن.
"""

# --- رنگ‌های کارت (گرادیان مورب: روشن -> تیره) ---
CARD_CREAM = ("#ded0b0", "#b8a179")       # فاش‌نشده / خنثی
CARD_RED = ("#c85a30", "#a34a26")         # فاش‌شده - تیم قرمز
CARD_BLUE = ("#1f8fa3", "#166778")        # فاش‌شده - تیم آبی
CARD_ASSASSIN = ("#2e2e2e", "#161616")    # فاش‌شده - قاتل

CARD_BORDER_CREAM = "#c9b48e"
CARD_BORDER_RED = "#8a3a1f"
CARD_BORDER_BLUE = "#0f4f5c"
CARD_BORDER_ASSASSIN = "#000000"

TEXT_DARK = "#3a2f22"       # متن روی کارت‌های کرم
TEXT_WHITE = "#ffffff"      # متن روی کارت‌های رنگی و قاتل

# --- رنگ‌های پنل تیم ---
PANEL_BLUE = "#003e9b"
PANEL_RED = "#c74201"

# --- پس‌زمینه‌ی کل تصویر (بسته به نوبت) ---
BG_BLUE_TURN = ("#4a7ab8", "#1e3f70")
BG_RED_TURN = ("#c1603a", "#8a3a1f")
BG_GRAY_ASSASSIN = ("#5a5f66", "#2b2e33")

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

# --- اندازه‌های چیدمان (پیکسل) ---
CANVAS_W = 1600
CANVAS_H = 1500

GRID_COLS = 5
GRID_ROWS = 5
CARD_W = 210
CARD_H = 130
CARD_GAP = 14
CARD_RADIUS = 16

PANEL_W = 300
PANEL_RADIUS = 24

MARGIN_TOP = 160   # فضای بالای تصویر برای شماره‌ی راند
MARGIN_BOTTOM = 140  # فضای پایین برای مربع عدد + مستطیل کلمه‌ی سرنخ
