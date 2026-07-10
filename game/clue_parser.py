"""
پارس کردن پیام ریپلای اسپای‌مستر (جاسوس) روی پیام بازی توی گروه.
فرمت مورد انتظار: عدد + فاصله(ی دلخواه/نیم‌فاصله/بدون فاصله) + کلمه‌ی سرنخ + ستاره‌ی اختیاری
مثال: "2 طبیعت"، "2طبیعت"، "۲ طبیعت"، "2‌طبیعت" (نیم‌فاصله)، "2  طبیعت" (دو فاصله)
مثال با قانون ستاره: "3 دریا *"، "4 دریا **" (یعنی یکی/دوتا از کارت‌های نوبت قبل هنوز مونده)
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

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

# کاراکترهایی که به‌عنوان «ستاره» (قانون ستاره) قبول می‌شن: * معمولی یا ایموجی ⭐
_STAR_CHARS = "*\u2b50"


class ParsedClue(NamedTuple):
    number: int
    word: str
    stars: int  # تعداد ستاره (کارت‌های باقی‌مانده از نوبت قبل)


def _normalize_digits(text: str) -> str:
    """عدد فارسی/عربی رو به عدد انگلیسی تبدیل می‌کنه."""
    return text.translate(_DIGIT_TRANSLATION)


def _normalize_invisible_spaces(text: str) -> str:
    """کاراکترهای فاصله‌مانند نامرئی رو با فاصله‌ی معمولی جایگزین می‌کنه."""
    for ch in _INVISIBLE_OR_SPACE_CHARS:
        text = text.replace(ch, " ")
    return text


def parse_clue(raw_text: Optional[str]) -> Optional[ParsedClue]:
    """
    ورودی: متن خام پیام ریپلای‌شده
    خروجی: ParsedClue(number, word, stars) یا None اگر فرمت نامعتبر بود
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

    number_str, rest = match.groups()
    rest = rest.strip()
    if not rest:
        return None

    # ستاره(های) انتهایی (قانون ستاره) رو از آخر کلمه جدا کن
    star_match = re.match(
        rf"^(.*?)\s*([{_STAR_CHARS}](?:\s*[{_STAR_CHARS}])*)\s*$", rest, flags=re.DOTALL
    )
    if star_match:
        candidate_word = star_match.group(1).strip()
        if not candidate_word:
            # کل متنِ بعد از عدد فقط ستاره بوده، کلمه‌ی واقعی‌ای وجود نداره
            return None
        word = candidate_word
        stars = sum(1 for ch in star_match.group(2) if ch in _STAR_CHARS)
    else:
        word = rest
        stars = 0

    try:
        number = int(number_str)
    except ValueError:
        return None

    return ParsedClue(number, word, stars)