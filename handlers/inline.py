"""
حالتِ Inline: وقتی کاربر توی هر چتی می‌نویسه "@آیدی‌ربات" (با یه فاصله بعدش)،
سه گزینه‌ی سطحِ دشواری نشون داده می‌شه. با زدنِ هرکدوم، یه پیامِ متنی (که دستورِ
مخصوصِ همون سطحه، مثلِ /codenames_easy) از طرفِ خودِ کاربر توی چت فرستاده می‌شه؛
handlers/commands.py با دیدنِ این دستور، لابیِ عادی رو با اون سطح می‌سازه - یعنی
هیچ زیرساختِ جدیدی (مثلِ ویرایشِ پیام‌های inline) لازم نیست، فقط یه میان‌بر برای
فرستادنِ دستورِ درسته.

نکته: برای فعال‌شدنِ این قابلیت، باید حالتِ Inline توی BotFather برای ربات روشن
بشه (دستورِ /setinline توی چت با @BotFather).

آیکونِ کوچیک (thumbnail_url): هرکدوم از URLهای پایین رو با آدرسِ واقعیِ عکسِ خودت
جایگزین کن. باید یه آدرسِ اینترنتیِ *عمومی* باشه (نه فایلِ لوکال) - مثلاً اگه
ریپازیتوریِ گیت‌هابت پابلیکه، می‌تونی عکس رو تو یه پوشه (مثلاً assets/images/)
بذاری و از لینکِ raw.githubusercontent.com استفاده کنی:
https://raw.githubusercontent.com/USERNAME/REPO/main/assets/images/easy.png
"""
from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

router = Router(name="inline")

_OPTIONS = [
    (
        "easy",
        "🟢 شروع بازی - سطح آسون",
        "کلمات هر تیم با هم ربط دارن، حدس‌زدن راحت‌تره",
        "/codenames_easy",
        "https://raw.githubusercontent.com/USERNAME/REPO/main/assets/images/easy.png",
    ),
    (
        "medium",
        "🟡 شروع بازی - سطح متوسط",
        "یه‌کم ربطِ ظریف بینِ کلمات هست، نه کاملاً رندوم",
        "/codenames_medium",
        "https://raw.githubusercontent.com/USERNAME/REPO/main/assets/images/medium.png",
    ),
    (
        "hard",
        "🔴 شروع بازی - سطح سخت",
        "کلمات کاملاً رندومن، همون بازیِ اصلیِ کدنیم",
        "/codenames_hard",
        "https://raw.githubusercontent.com/USERNAME/REPO/main/assets/images/hard.png",
    ),
]


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery) -> None:
    results = [
        InlineQueryResultArticle(
            id=key,
            title=title,
            description=description,
            input_message_content=InputTextMessageContent(message_text=command_text),
            thumbnail_url=thumb_url,
            thumbnail_width=128,
            thumbnail_height=128,
        )
        for key, title, description, command_text, thumb_url in _OPTIONS
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)