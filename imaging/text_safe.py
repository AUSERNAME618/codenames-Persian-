"""
پاک‌سازیِ متنِ ورودیِ کاربر قبل از رسم روی تصویر.

مشکل: اسمِ بازیکن‌ها (که از full_name تلگرام میاد) یا کلمه‌ی سرنخ می‌تونه
شامل ایموجی یا کاراکترهای یونیکدِ عجیب باشه که فونت‌های Pofak پشتیبانی
نمی‌کنن. Pillow برای هر گلیفِ گمشده یه مربعِ توخالی (tofu) رسم می‌کنه که
خیلی زشت به نظر می‌رسه و باگ محسوب می‌شه.

راه‌حل: قبل از هر draw.text، متن رو از این تابع رد می‌کنیم تا هر کاراکتری
که فونت پشتیبانی نمی‌کنه حذف بشه (نه اینکه با یه علامتِ دیگه جایگزین بشه،
چون معمولاً بهتره کلاً حذف بشه تا فاصله‌های عجیب نمونه).
"""
from __future__ import annotations

from functools import lru_cache

from fontTools.ttLib import TTFont

# کاراکترهایی که همیشه مجازن، حتی اگه توی cmap فونت به‌طور دقیق چک نشن
# (فاصله‌ی معمولی، نیم‌فاصله، و غیره - چون این‌ها معمولاً مشکلی ایجاد نمی‌کنن)
_ALWAYS_ALLOWED = {" ", "\u200c", "\n", "\t"}


@lru_cache(maxsize=8)
def _font_cmap(font_path: str) -> frozenset[int]:
    """کدپوینت‌هایی که یه فونتِ TTF پشتیبانی می‌کنه رو کش می‌کنه."""
    try:
        tt = TTFont(font_path, lazy=True)
        cmap = tt.getBestCmap()
        return frozenset(cmap.keys())
    except Exception:
        # اگه به هر دلیلی فونت لود نشد، خیلی محافظه‌کارانه فرض کن هیچی رو
        # فیلتر نکنه (بهتره یه گلیفِ عجیب رد بشه تا کل برنامه کرش کنه)
        return frozenset(range(0x110000))


def sanitize_for_font(text: str | None, font_path: str) -> str:
    """
    هر کاراکتری که توی فونتِ داده‌شده گلیف نداره رو از متن حذف می‌کنه.
    برای اسمِ بازیکن‌ها، کلمه‌ی سرنخ، و هر متنِ ورودیِ کاربر که قراره
    روی تصویر رسم بشه استفاده کن.
    """
    if not text:
        return text or ""
    allowed_codes = _font_cmap(font_path)
    cleaned = "".join(
        ch for ch in text
        if ch in _ALWAYS_ALLOWED or ord(ch) in allowed_codes
    )
    # فقط فاصله‌های معمولیِ پشت‌سرهم رو یکی کن (نه نیم‌فاصله/ZWNJ، که برای
    # چسبیدن درستِ کلمات فارسی لازمه و نباید بهش دست بزنیم)
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned.strip()
