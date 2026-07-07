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
from handlers import commands, lobby
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


async def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise RuntimeError(
            "توکن ربات ست نشده. متغیر محیطی BOT_TOKEN رو با توکن واقعی از BotFather پر کن."
        )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(lobby.router)
    dp.include_router(game_handlers.router)

    db_pool = await init_db(DATABASE_URL)
    logger.info("اتصال به دیتابیس Postgres برقرار شد.")

    port = int(os.getenv("PORT", "8080"))
    await _run_keepalive_server(port)

    logger.info("ربات در حال شروع Long Polling...")
    try:
        await dp.start_polling(bot, db_conn=db_pool)
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
