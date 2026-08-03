"""
نقطه‌ی ورود اصلی ربات.
اجرا: python3 bot.py
"""
import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, DATABASE_URL
from database.db import init_db
from database.repository import delete_stale_lobbies
from handlers import commands, lobby, help as help_handlers, inline as inline_handlers
from handlers import game as game_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("codenames_bot")


async def _health_check(request: web.Request) -> web.Response:
    """
    اندپوینت سلامت. برای Render + UptimeRobot لازمه:
    Render فقط با دیدن ترافیک HTTP ورودی، سرویس رو زنده نگه می‌داره.
    """
    return web.Response(text="OK")


async def _run_keepalive_server(port: int) -> None:
    app = web.Application()
    app.router.add_get("/", _health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"سرور keep-alive روی پورت {port} بالا اومد.")


async def _run_periodic_cleanup(db_pool, interval_hours: int = 6) -> None:
    """هر چند ساعت یه‌بار، لابی‌های رهاشده (هیچ‌وقت بازی نشدن) رو پاک می‌کنه."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            deleted = await delete_stale_lobbies(db_pool)
            if deleted:
                logger.info(f"پاک‌سازیِ دوره‌ای: {deleted} لابیِ رهاشده حذف شد.")
        except Exception:
            logger.exception("خطا در پاک‌سازیِ دوره‌ای لابی‌ها")


async def _run_db_keepalive(db_pool, interval_minutes: int = 4) -> None:
    """
    هر چند دقیقه یه کوئریِ خیلی سبک (SELECT 1) می‌زنه تا دیتابیسِ سرورلس (مثلاً Neon)
    به‌خاطرِ بی‌کاری suspend نشه. اگه دیتابیس suspend بشه، اولین کوئریِ بعدش می‌تونه
    چند ثانیه طول بکشه (cold start) - که دقیقاً یکی از منابعِ احتمالیِ کندیِ گاه‌به‌گاهه.
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
        except Exception:
            logger.exception("خطا در پینگِ نگه‌داشتنِ دیتابیس")


async def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise RuntimeError(
            "توکن ربات ست نشده. متغیر محیطی BOT_TOKEN رو با توکن واقعی از BotFather پر کن."
        )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(help_handlers.router)
    dp.include_router(lobby.router)
    dp.include_router(game_handlers.router)
    dp.include_router(inline_handlers.router)

    db_pool = await init_db(DATABASE_URL)
    logger.info("اتصال به دیتابیس Postgres برقرار شد.")

    port = int(os.getenv("PORT", "8080"))
    await _run_keepalive_server(port)

    asyncio.create_task(_run_periodic_cleanup(db_pool))
    asyncio.create_task(_run_db_keepalive(db_pool))

    logger.info("ربات در حال شروع Long Polling...")
    try:
        # قبل از شروعِ polling، هر آپدیتِ عقب‌مونده‌ی حینِ خاموشی/ری‌استارت رو دور
        # می‌ریزیم - وگرنه مثلاً چندتا /codenames که حینِ داون‌بودنِ ربات فرستاده شدن،
        # یهو همه‌شون با هم پردازش می‌شن و باعثِ اسپمِ چندین لابیِ پشتِ‌سرِهم می‌شن.
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, db_conn=db_pool)
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())