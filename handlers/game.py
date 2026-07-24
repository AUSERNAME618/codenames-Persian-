"""
هندلرهای حین بازی: کلیک روی کلمه (حدس)، پایان دست، اتمام حدس،
و پردازش ریپلای متنی جاسوس روی پیام پنل بازی (عدد + کلمه‌ی سرنخ).
"""
from __future__ import annotations

import asyncpg
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message

from database.repository import save_game, load_game, load_active_game_by_chat
from game.state import GameError, GameStatus, Role, CardColor
from game.clue_parser import parse_clue
from handlers.game_flow import sync_board_message

router = Router(name="game")

_GUESS_FEEDBACK = {
    CardColor.RED: "🟥 قرمز بود!",
    CardColor.BLUE: "🟦 آبی بود!",
    CardColor.NEUTRAL: "⬜ خنثی بود.",
    CardColor.ASSASSIN: "⬛ قاتل بود! 💀 باختید!",
}


def _is_current_operative(game, user_id: int) -> bool:
    player = game.players.get(user_id)
    return (
        player is not None
        and player.role == Role.OPERATIVE
        and player.team == game.current_turn
    )


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """دکمه‌های تزئینی/غیرقابل‌کلیک - کاری انجام نمی‌دن."""
    await callback.answer()


@router.callback_query(F.data.startswith("board:"))
async def handle_board_callback(
    callback: CallbackQuery, bot: Bot, db_conn: asyncpg.Pool
) -> None:
    parts = callback.data.split(":")
    game_id = parts[1]
    action = parts[2]

    game = await load_game(db_conn, game_id)
    if game is None:
        await callback.answer("این بازی دیگه وجود نداره.", show_alert=True)
        return

    user_id = callback.from_user.id

    if action == "guess":
        idx = int(parts[3])
        if not _is_current_operative(game, user_id):
            await callback.answer("نوبت شما نیست یا مامور این تیم نیستید.", show_alert=True)
            return

        turn_before = game.current_turn
        try:
            color = game.guess(idx, callback.from_user.full_name)
        except GameError as e:
            await callback.answer(str(e), show_alert=True)
            return

        turn_changed = (game.status == GameStatus.FINISHED) or (game.current_turn != turn_before)
        await save_game(db_conn, game)
        await sync_board_message(bot, db_conn, game, move_to_bottom=turn_changed)
        await callback.answer(_GUESS_FEEDBACK[color])
        return

    if action == "endturn":
        if not _is_current_operative(game, user_id):
            await callback.answer("نوبت شما نیست یا مامور این تیم نیستید.", show_alert=True)
            return
        try:
            game.end_turn()
        except GameError as e:
            await callback.answer(str(e), show_alert=True)
            return
        await save_game(db_conn, game)
        await sync_board_message(bot, db_conn, game, move_to_bottom=True)
        await callback.answer("نوبت به تیم مقابل منتقل شد.")
        return

    if action == "endguess":
        if not _is_current_operative(game, user_id):
            await callback.answer("نوبت شما نیست یا مامور این تیم نیستید.", show_alert=True)
            return
        try:
            game.end_guessing()
        except GameError as e:
            await callback.answer(str(e), show_alert=True)
            return
        await save_game(db_conn, game)
        await sync_board_message(bot, db_conn, game, move_to_bottom=True)
        await callback.answer("نوبت به تیم مقابل منتقل شد.")
        return

    if action == "movebottom":
        if user_id != game.host_id:
            await callback.answer("فقط سازنده‌ی بازی می‌تونه پنل رو جابه‌جا کنه.", show_alert=True)
            return
        await sync_board_message(bot, db_conn, game, move_to_bottom=True)
        await callback.answer("پنل به آخرین پیام منتقل شد.")
        return

    await callback.answer()


@router.message(F.reply_to_message, F.chat.type.in_({"group", "supergroup"}))
async def handle_clue_reply(message: Message, bot: Bot, db_conn: asyncpg.Pool) -> None:
    """
    وقتی جاسوس روی پیام پنل بازی ریپلای می‌کنه: 'عدد + کلمه‌ی سرنخ' (مثلاً '2 طبیعت').
    """
    game = await load_active_game_by_chat(db_conn, message.chat.id)
    if game is None:
        return
    if message.reply_to_message.message_id != game.last_message_id:
        return
    if game.status != GameStatus.AWAITING_CLUE:
        return

    player = game.players.get(message.from_user.id)
    if player is None or player.role != Role.SPYMASTER or player.team != game.current_turn:
        # این ریپلای مربوط به جاسوسِ نوبتِ فعلی نیست - نادیده می‌گیریم (نه خطا)
        return

    parsed = parse_clue(message.text)
    if parsed is None:
        await message.reply("❌ فرمت درست نیست. اول عدد، بعد کلمه‌ی سرنخ. مثلاً: 2 طبیعت")
        return

    n, word, stars = parsed
    try:
        game.set_clue_count(n, word, stars)
    except GameError as e:
        await message.reply(str(e))
        return

    await save_game(db_conn, game)
    await sync_board_message(bot, db_conn, game, move_to_bottom=False)
    star_note = "*" * stars
    await message.reply(f"✅ سرنخ ثبت شد: «{word}{star_note}» ({n}) — نوبت حدس‌زدنه!")