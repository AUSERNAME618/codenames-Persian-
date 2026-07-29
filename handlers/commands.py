"""
دستورهای متنی ربات.
/codenames یه لابیِ جدید با سطحِ سخت می‌سازه (پیش‌فرض).
/codenames_easy، /codenames_medium، /codenames_hard همون کار رو با سطحِ مشخص‌شده
انجام می‌دن - این‌ها همون چیزی هستن که وقتی کاربر از حالتِ Inline (نوشتنِ @آیدی‌ربات
و انتخابِ یه سطح) استفاده می‌کنه، به‌عنوانِ پیام توی گروه فرستاده می‌شن.
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


async def _create_lobby(message: Message, db_conn: asyncpg.Pool, difficulty: str) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("این بازی فقط توی گروه قابل بازی کردنه، نه در چت خصوصی.")
        return

    game = Game(
        game_id=generate_game_id(),
        chat_id=message.chat.id,
        host_id=message.from_user.id,
        team_size_mode=4,
    )
    game.difficulty = difficulty
    sent = await message.answer(
        "🎮 یه بازی کدنیم جدید ساخته شد! نقش خودتون رو انتخاب کنید:",
        reply_markup=to_aiogram_markup(build_lobby_rows(game)),
    )
    game.last_message_id = sent.message_id
    await save_game(db_conn, game)

    await message.answer(
        "💡 اولین بارتونه بازی می‌کنید؟ دستور /راهنما رو بفرستید توی گروه تا با "
        "قوانین کدنیم و طرز کار ربات آشنا بشید."
    )


@router.message(Command("codenames"))
async def cmd_new_game(message: Message, db_conn: asyncpg.Pool) -> None:
    await _create_lobby(message, db_conn, difficulty="hard")


@router.message(Command("codenames_easy"))
async def cmd_new_game_easy(message: Message, db_conn: asyncpg.Pool) -> None:
    await _create_lobby(message, db_conn, difficulty="easy")


@router.message(Command("codenames_medium"))
async def cmd_new_game_medium(message: Message, db_conn: asyncpg.Pool) -> None:
    await _create_lobby(message, db_conn, difficulty="medium")


@router.message(Command("codenames_hard"))
async def cmd_new_game_hard(message: Message, db_conn: asyncpg.Pool) -> None:
    await _create_lobby(message, db_conn, difficulty="hard")