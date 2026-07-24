"""
هندلرهای مربوط به لابی: نشستن روی اسلات، تغییر نفرات، شروع بازی، خروج (چندکاره).
"""
from __future__ import annotations

import json

import asyncpg
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import WORDS_PATH
from database.repository import save_game, load_game, delete_game
from game.state import Game, GameError, Role, Team
from keyboards.lobby import build_lobby_rows
from keyboards.types import to_aiogram_markup
from handlers.game_flow import begin_game

router = Router(name="lobby")


def _load_word_pool() -> list[str]:
    with open(WORDS_PATH, encoding="utf-8") as f:
        return json.load(f)


async def _refresh_lobby_message(bot: Bot, game: Game) -> None:
    """پیام لابی گروه رو با کیبورد جدید (بعد از هر تغییری) ادیت می‌کنه."""
    rows = build_lobby_rows(game)
    markup = to_aiogram_markup(rows)
    try:
        await bot.edit_message_reply_markup(
            chat_id=game.chat_id,
            message_id=game.last_message_id,
            reply_markup=markup,
        )
    except TelegramBadRequest:
        # اگه محتوا/کیبورد قبلی دقیقاً یکی بود، تلگرام ارور "not modified" می‌ده - بی‌خطره
        pass


@router.callback_query(F.data.startswith("lobby:"))
async def handle_lobby_callback(callback: CallbackQuery, bot: Bot, db_conn: asyncpg.Pool) -> None:
    parts = callback.data.split(":")
    # ساختار: lobby:{game_id}:{action}[:...]
    game_id = parts[1]
    action = parts[2]

    conn = db_conn
    game = await load_game(conn, game_id)
    if game is None:
        await callback.answer("این بازی دیگه وجود نداره.", show_alert=True)
        return

    user_id = callback.from_user.id
    user_name = callback.from_user.full_name

    # ---------- نشستن روی اسلات ----------
    if action == "join":
        team = Team(parts[3])
        role = Role(parts[4])
        slot = int(parts[5])
        try:
            game.join_slot(user_id, user_name, team, role, slot)
        except GameError as e:
            await callback.answer(str(e), show_alert=True)
            return
        await save_game(conn, game)
        await _refresh_lobby_message(bot, game)
        await callback.answer()
        return

    # ---------- تغییر نفرات (فقط سازنده) ----------
    if action == "cycle":
        if user_id != game.host_id:
            await callback.answer("فقط سازنده‌ی بازی می‌تونه تعداد نفرات رو عوض کنه.", show_alert=True)
            return
        game.cycle_team_size()
        await save_game(conn, game)
        await _refresh_lobby_message(bot, game)
        await callback.answer(f"حالت {game.team_size_mode} نفره شد.")
        return

    # ---------- شروع بازی (فقط سازنده) ----------
    if action == "start":
        if user_id != game.host_id:
            await callback.answer("فقط سازنده‌ی بازی می‌تونه بازی رو شروع کنه.", show_alert=True)
            return
        if not game.is_ready_to_start():
            await callback.answer("نفرات کافی نیست! هر تیم باید حداقل یه جاسوس و یه مامور داشته باشه.", show_alert=True)
            return
        word_pool = _load_word_pool()
        game.start_game(word_pool)
        await save_game(conn, game)
        await begin_game(bot, conn, game)
        await callback.answer("بازی شروع شد!")
        return

    # ---------- خروج (چندکاره) ----------
    if action == "exit":
        if user_id == game.host_id:
            # سازنده: کل بازی پاک می‌شه و یه روم جدید و خالی جایگزینش می‌شه
            await delete_game(conn, game_id)
            try:
                await bot.delete_message(chat_id=game.chat_id, message_id=game.last_message_id)
            except TelegramBadRequest:
                pass

            from game.idgen import generate_game_id

            new_game = Game(
                game_id=generate_game_id(),
                chat_id=game.chat_id,
                host_id=game.host_id,
                team_size_mode=4,
            )
            sent = await bot.send_message(
                chat_id=game.chat_id,
                text="🎮 یه بازی جدید کدنیم ساخته شد! نقش خودتون رو انتخاب کنید:",
                reply_markup=to_aiogram_markup(build_lobby_rows(new_game)),
            )
            new_game.last_message_id = sent.message_id
            await save_game(conn, new_game)
            await callback.answer("بازی بسته شد و یه روم جدید باز شد.")
            return

        # پلیر معمولی که توی یه اسلاته -> فقط خودش خارج می‌شه
        if user_id in game.players:
            game.remove_player(user_id)
            await save_game(conn, game)
            await _refresh_lobby_message(bot, game)
            await callback.answer("از بازی خارج شدید، می‌تونید دوباره یه نقش انتخاب کنید.")
            return

        # پلیری که اصلاً تو هیچ اسلاتی نبوده
        await callback.answer("شما توی این بازی نیستید.", show_alert=True)
        return

    await callback.answer()
