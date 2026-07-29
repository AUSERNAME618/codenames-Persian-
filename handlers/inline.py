"""
حالتِ Inline: وقتی کاربر توی هر چتی می‌نویسه "@آیدی‌ربات" (با یه فاصله بعدش)،
سه گزینه‌ی سطحِ دشواری نشون داده می‌شه. با زدنِ هرکدوم، یه پیامِ متنی (که دستورِ
مخصوصِ همون سطحه، مثلِ /codenames_easy) از طرفِ خودِ کاربر توی چت فرستاده می‌شه؛
handlers/commands.py با دیدنِ این دستور، لابیِ عادی رو با اون سطح می‌سازه - یعنی
هیچ زیرساختِ جدیدی (مثلِ ویرایشِ پیام‌های inline) لازم نیست، فقط یه میان‌بر برای
فرستادنِ دستورِ درسته.

نکته: برای فعال‌شدنِ این قابلیت، باید حالتِ Inline توی BotFather برای ربات روشن
بشه (دستورِ /setinline توی چت با @BotFather).
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
    ),
    (
        "medium",
        "🟡 شروع بازی - سطح متوسط",
        "یه‌کم ربطِ ظریف بینِ کلمات هست، نه کاملاً رندوم",
        "/codenames_medium",
    ),
    (
        "hard",
        "🔴 شروع بازی - سطح سخت",
        "کلمات کاملاً رندومن، همون بازیِ اصلیِ کدنیم",
        "/codenames_hard",
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
        )
        for key, title, description, command_text in _OPTIONS
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)
