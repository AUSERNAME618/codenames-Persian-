"""
توابع CRUD برای ذخیره و بازیابی وضعیت بازی در Postgres (از طریق asyncpg pool).
هر بازی به‌صورت یک ردیف با کل state سریالایزشده (JSON) نگه داشته می‌شود.
"""
from typing import Optional

import asyncpg

from game.state import Game


async def save_game(pool: asyncpg.Pool, game: Game) -> None:
    """بازی را ذخیره می‌کند (اگر وجود داشت آپدیت، وگرنه insert)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO games (game_id, chat_id, host_id, status, state_json, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (game_id) DO UPDATE SET
                chat_id = EXCLUDED.chat_id,
                host_id = EXCLUDED.host_id,
                status = EXCLUDED.status,
                state_json = EXCLUDED.state_json,
                updated_at = NOW()
            """,
            game.game_id,
            game.chat_id,
            game.host_id,
            game.status.value,
            game.to_json(),
        )


async def load_game(pool: asyncpg.Pool, game_id: str) -> Optional[Game]:
    """یک بازی را با game_id بارگذاری می‌کند."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT state_json FROM games WHERE game_id = $1", game_id
        )
    if row is None:
        return None
    return Game.from_json(row["state_json"])


async def load_active_game_by_chat(pool: asyncpg.Pool, chat_id: int) -> Optional[Game]:
    """
    آخرین بازی ثبت‌شده برای این چت را برمی‌گرداند (بازی فعال گروه).
    فرض: در هر چت گروهی، در هر لحظه فقط یک بازی فعال داریم.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT state_json FROM games
            WHERE chat_id = $1 AND status != 'finished'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            chat_id,
        )
    if row is None:
        return None
    return Game.from_json(row["state_json"])


async def delete_game(pool: asyncpg.Pool, game_id: str) -> None:
    """بازی را کامل حذف می‌کند (مثلاً وقتی هاست دکمه‌ی «خروج» را می‌زند)."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM games WHERE game_id = $1", game_id)
