"""
ButtonSpec: نمایش خالص و مستقل از aiogram برای یک دکمه‌ی شیشه‌ای.
این جدایی باعث می‌شه منطق چیدمان کیبورد (کدوم دکمه کجا، چه متنی، چه رنگی)
بدون نیاز به نصب واقعی aiogram قابل تست باشه.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ButtonSpec:
    text: str
    callback_data: Optional[str] = None
    style: Optional[str] = None  # "danger" | "primary" | "success" | None
    switch_inline_query_current_chat: Optional[str] = None

    def is_noop(self) -> bool:
        """دکمه‌ی صرفاً نمایشی (غیرقابل کلیک از نظر منطقی)."""
        return self.callback_data == "noop"


# نوع کمکی: یک ردیف از دکمه‌ها، و کل کیبورد = لیستی از ردیف‌ها
Row = list[ButtonSpec]
Rows = list[Row]


def to_aiogram_markup(rows: Rows):
    """
    Rows (خالص و تست‌پذیر) رو به InlineKeyboardMarkup واقعی aiogram تبدیل می‌کنه.
    این تابع خودش منطقی نداره، فقط یه تبدیل مستقیمه؛ بخش تست‌شونده جای دیگه‌ست.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = []
    for row in rows:
        keyboard_row = []
        for btn in row:
            kwargs = {"text": btn.text}
            if btn.switch_inline_query_current_chat is not None:
                kwargs["switch_inline_query_current_chat"] = btn.switch_inline_query_current_chat
            else:
                kwargs["callback_data"] = btn.callback_data or "noop"
            if btn.style is not None:
                # فیلد style مربوط به Bot API 9.4 (فوریه ۲۰۲۶) است.
                # اگر نسخه‌ی aiogram نصب‌شده هنوز این فیلد را پشتیبانی نکند،
                # این خط را موقتاً حذف کنید تا خطا ندهد.
                kwargs["style"] = btn.style
            keyboard_row.append(InlineKeyboardButton(**kwargs))
        keyboard.append(keyboard_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
