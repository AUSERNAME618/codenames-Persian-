"""
هندلرهای مربوط به لابی: نشستن روی اسلات، تغییر نفرات، شروع بازی، خروج (چندکاره).

نکته‌ی صحت/کارایی: قفلِ per-game (game/locks.py) فقط دورِ بخشِ سریعِ
load->تغییر->answer->save کشیده می‌شه، نه دورِ ادیت/ارسالِ پیام (که شبکه‌ایه و
می‌تونه کند بشه). اگه قفل دورِ اون بخشِ کند هم کشیده بشه، اکشن‌های بعدیِ روی همون
بازی (مثلاً چندنفر که هم‌زمان دارن جوین می‌دن) باید صف بشن تا حتی جوابِ اولیه‌شون
دیر برسه - که خودش باعثِ منقضی‌شدنِ callback query میشه (چون تلگرام باید سریع
جواب بگیره).
"""
from __future__ import annotations

import json

import asyncpg
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import WORDS_PATH, WORD_CLUSTERS_PATH
from database.repository import save_game, load_game, delete_game
from game.state import Game, GameError, Role, Team
from game.locks import get_game_lock, drop_game_lock, is_duplicate_callback
from keyboards.lobby import build_lobby_rows
from keyboards.types import to_aiogram_markup
from handlers.game_flow import begin_game, send_lobby_message

router = Router(name="lobby")


def _load_word_pool() -> list[str]:
    with open(WORDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_word_clusters() -> list[dict]:
    with open(WORD_CLUSTERS_PATH, encoding="utf-8") as f:
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
    if is_duplicate_callback(callback.id):
        return

    parts = callback.data.split(":")
    # ساختار: lobby:{game_id}:{action}[:...]
    game_id = parts[1]
    action = parts[2]
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name

    # وضعیتی که بعدِ آزادشدنِ قفل لازم داریم (برای refresh/begin_game/... بیرونِ قفل)
    need_refresh = False
    need_begin_game = False
    exit_as_host = False
    game: Game | None = None

    async with get_game_lock(game_id):
        conn = db_conn
        game = await load_game(conn, game_id)
        if game is None:
            await callback.answer("این بازی دیگه وجود نداره.", show_alert=True)
            return

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
            await callback.answer()
            await save_game(conn, game)
            need_refresh = True

        # ---------- تغییر نفرات (فقط سازنده) ----------
        elif action == "cycle":
            if user_id != game.host_id:
                await callback.answer("فقط سازنده‌ی بازی می‌تونه تعداد نفرات رو عوض کنه.", show_alert=True)
                return
            game.cycle_team_size()
            await callback.answer(f"حالت {game.team_size_mode} نفره شد.")
            await save_game(conn, game)
            need_refresh = True

        # ---------- تغییر سطح دشواری (فقط سازنده) ----------
        elif action == "cycle_difficulty":
            if user_id != game.host_id:
                await callback.answer("فقط سازنده‌ی بازی می‌تونه سطح دشواری رو عوض کنه.", show_alert=True)
                return
            game.cycle_difficulty()
            from config import DIFFICULTY_LABELS_FA
            await callback.answer(f"سطح دشواری: {DIFFICULTY_LABELS_FA.get(game.difficulty, game.difficulty)}")
            await save_game(conn, game)
            need_refresh = True

        # ---------- شروع بازی (فقط سازنده) ----------
        elif action == "start":
            if user_id != game.host_id:
                await callback.answer("فقط سازنده‌ی بازی می‌تونه بازی رو شروع کنه.", show_alert=True)
                return
            if not game.is_ready_to_start():
                await callback.answer("نفرات کافی نیست! هر تیم باید حداقل یه جاسوس و یه مامور داشته باشه.", show_alert=True)
                return
            word_pool = _load_word_pool()
            clusters = _load_word_clusters() if game.difficulty != "hard" else []
            game.start_game(word_pool, clusters)
            await callback.answer("بازی شروع شد!")
            await save_game(conn, game)
            need_begin_game = True

        # ---------- خروج (چندکاره) ----------
        elif action == "exit":
            if user_id == game.host_id:
                await callback.answer("بازی بسته شد و یه روم جدید باز شد.")
                await delete_game(conn, game_id)
                drop_game_lock(game_id)
                exit_as_host = True
            elif user_id in game.players:
                game.remove_player(user_id)
                await callback.answer("از بازی خارج شدید، می‌تونید دوباره یه نقش انتخاب کنید.")
                await save_game(conn, game)
                need_refresh = True
            else:
                await callback.answer("شما توی این بازی نیستید.", show_alert=True)
                return

        else:
            await callback.answer()
            return

    # --- قفل اینجا آزاد شده - ادیت/ارسالِ پیام بیرونِ قفل انجام می‌شه ---
    if need_refresh:
        await _refresh_lobby_message(bot, game)
    elif need_begin_game:
        await begin_game(bot, db_conn, game)
    elif exit_as_host:
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
        sent = await send_lobby_message(
            bot,
            game.chat_id,
            "🎮 یه بازی جدید کدنیم ساخته شد! نقش خودتون رو انتخاب کنید:",
            to_aiogram_markup(build_lobby_rows(new_game)),
        )
        new_game.last_message_id = sent.message_id
        await save_game(db_conn, new_game)
