"""
هندلر اینلاین ربات کدنیمز
"""
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

router = Router(name="inline")


@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    results = [
        InlineQueryResultArticle(
            id="mode_easy",
            title="کدنیمز - آسان 🟢",
            description="کلمات ساده و آشنا مناسب برای بازی‌های سریع و مبتدی",
            thumbnail_url="https://raw.githubusercontent.com/AUSERNAME618/codenames-Persian-/main/assets/images/easy.png",
            input_message_content=InputTextMessageContent(
                message_text="/codenames easy"
            ),
        ),
        InlineQueryResultArticle(
            id="mode_medium",
            title="کدنیمز - متوسط 🟡",
            description="ترکیب کلمات عمومی و چالشی، استاندارد و پرهیجان",
            thumbnail_url="https://raw.githubusercontent.com/AUSERNAME618/codenames-Persian-/main/assets/images/medium.png",
            input_message_content=InputTextMessageContent(
                message_text="/codenames medium"
            ),
        ),
        InlineQueryResultArticle(
            id="mode_hard",
            title="کدنیمز - سخت 🔴",
            description="کلمات مفهومی و دوپهلو، نیازمند تمرکز و هوش بالا",
            thumbnail_url="https://raw.githubusercontent.com/AUSERNAME618/codenames-Persian-/main/assets/images/hard.png",
            input_message_content=InputTextMessageContent(
                message_text="/codenames hard"
            ),
        ),
        InlineQueryResultArticle(
            id="mode_pictures",
            title="کدنیمز - تصویری 🖼",
            description="حالت رسمی Codenames: Pictures با ۲۰ کارت تصویری (شبکه ۵×۴)",
            thumbnail_url="https://raw.githubusercontent.com/AUSERNAME618/codenames-Persian-/main/assets/images/medium.png",
            input_message_content=InputTextMessageContent(
                message_text="/pictures"
            ),
        ),
    ]

    await inline_query.answer(results, cache_time=5, is_personal=True)
