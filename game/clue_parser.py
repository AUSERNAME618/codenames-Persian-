"""
پارس کردن پیام ریپلای اسپای‌مستر (جاسوس) روی پیام بازی توی گروه.
فرمت مورد انتظار: عدد + فاصله(ی دلخواه/نیم‌فاصله/بدون فاصله) + کلمه‌ی سرنخ
مثال: "2 طبیعت"، "2طبیعت"، "۲ طبیعت"، "2‌طبیعت" (نیم‌فاصله)، "2  طبیعت" (دو فاصله)
"""
from __future__ import annotations

import re
from typing import Optional

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
WESTERN_DIGITS = "0123456789"

_DIGIT_TRANSLATION = str.maketrans(
    PERSIAN_DIGITS + ARABIC_INDIC_DIGITS,
    WESTERN_DIGITS + WESTERN_DIGITS,
)

# کاراکترهای نامرئی یا فاصله‌مانندی که ممکنه کاربر اشتباهی بین عدد و کلمه بذاره
_INVISIBLE_OR_SPACE_CHARS = [
    "\u200c",  # نیم‌فاصله (ZWNJ) - رایج‌ترین اشتباه تایپی فارسی
    "\u200b",  # zero-width space
    "\u00a0",  # non-breaking space
    "\t",
]


def _normalize_digits(text: str) -> str:
    """عدد فارسی/عربی رو به عدد انگلیسی تبدیل می‌کنه."""
    return text.translate(_DIGIT_TRANSLATION)


def _normalize_invisible_spaces(text: str) -> str:
    """کاراکترهای فاصله‌مانند نامرئی رو با فاصله‌ی معمولی جایگزین می‌کنه."""
    for ch in _INVISIBLE_OR_SPACE_CHARS:
        text = text.replace(ch, " ")
    return text


def parse_clue(raw_text: Optional[str]) -> Optional[tuple[int, str]]:
    """
    ورودی: متن خام پیام ریپلای‌شده
    خروجی: (عدد_سرنخ, کلمه_سرنخ) یا None اگر فرمت نامعتبر بود
    """
    if not raw_text:
        return None

    text = raw_text.strip()
    if not text:
        return None

    text = _normalize_digits(text)
    text = _normalize_invisible_spaces(text)

    # عدد باید همون اول متن باشه (نه وسط یا آخر)؛ جداکننده می‌تونه فاصله، اسلش، یا نقطه باشه
    match = re.match(r"^\s*(\d+)[\s/.]*(.*)$", text, flags=re.DOTALL)
    if not match:
        return None

    number_str, word = match.groups()
    word = word.strip()
    if not word:
        return None

    try:
        number = int(number_str)
    except ValueError:
        return None

    return number, word
