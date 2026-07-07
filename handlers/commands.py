"""
دستورهای متنی ربات. فعلاً فقط /codenames برای ساخت یه لابی جدید.
"""
import asyncpg
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.repository import save_game
from game.state import Game
from game.idgen import generate_game_id
from keyboards.lobby import build_lobby_rows
from keyboards.types import to_aiogram_markup

router = Router(name="commands")


@router.message(Command("codenames"))
async def cmd_new_game(message: Message, db_conn: asyncpg.Pool) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("این بازی فقط توی گروه قابل بازی کردنه، نه در چت خصوصی.")
        return

    game = Game(
        game_id=generate_game_id(),
        chat_id=message.chat.id,
        host_id=message.from_user.id,
        team_size_mode=4,
    )
    sent = await message.answer(
        "🎮 یه بازی کدنیم جدید ساخته شد! نقش خودتون رو انتخاب کنید:",
        reply_markup=to_aiogram_markup(build_lobby_rows(game)),
    )
    game.last_message_id = sent.message_id
    await save_game(db_conn, game)
