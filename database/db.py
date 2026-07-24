"""
اتصال به Postgres (مثلاً Neon) و ساخت schema.
از asyncpg با یه connection pool استفاده می‌شه (نه یه کانکشن تکی)،
چون چندین هندلر aiogram ممکنه هم‌زمان بخوان کوئری بزنن.
"""
import asyncpg

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id     TEXT PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    host_id     BIGINT NOT NULL,
    status      TEXT NOT NULL,
    state_json  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_chat_id ON games(chat_id);
"""


async def init_db(database_url: str) -> asyncpg.Pool:
    """
    یه connection pool به Postgres می‌سازه و در صورت نبودن جدول، آن را می‌سازد.
    این pool باید در طول عمر ربات باز بماند (یک بار در bot.py فراخوانی شود).
    """
    pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA)
    return pool

