"""
هندلرهای حین بازی: کلیک روی کلمه (حدس)، پایان دست، اتمام حدس،
و پردازش ریپلای متنی جاسوس روی پیام پنل بازی (عدد + کلمه‌ی سرنخ).

چهار نکته‌ی مهمِ کارایی/صحت:

۱) callback.answer() بلافاصله بعدِ اعتبارسنجی و اعمالِ منطقِ بازی صدا زده می‌شه -
   قبل از رندر/ارسالِ سنگینِ عکس.

۲) قفلِ per-game (game/locks.py) فقط دورِ بخشِ *سریع* (load -> تغییر -> answer -> save)
   کشیده می‌شه - نه دورِ رندر/آپلودِ عکس.

۳) به‌جای این‌که sync_board_message همیشه دوباره از دیتابیس بخونه (یه رفت‌وبرگشتِ
   شبکه‌ای اضافه که چند صد میلی‌ثانیه تا حتی چند ثانیه طول می‌کشه)، توی حالتِ
   معمولی (بدونِ رقابتِ هم‌زمان) مستقیم همون آبجکتِ Game که تازه mutate/save
   کردیم رو می‌دیم. فقط وقتی coalesced_sync تشخیص بده یه اکشنِ دیگه هم‌زمان اومده
   (یعنی احتمالِ staleness هست)، اجرای دوم دوباره از دیتابیس می‌خونه.

۴) هر callback_query یه شناسه‌ی یکتا داره؛ اگه دقیقاً همون یکی دوبار به دستِ ما
   برسه (مثلاً تپِ خیلی سریعِ کاربر)، بارِ دوم نادیده گرفته می‌شه - از پیامِ تکراری
   جلوگیری می‌کنه، حتی مستقل از سرعتِ پاسخ‌گویی.
"""
from __future__ import annotations

import logging

import asyncpg
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message

from database.repository import save_game, load_game, load_active_game_by_chat
from game.state import Game, GameError, GameStatus, Role, CardColor
from game.clue_parser import parse_clue
from game.locks import get_game_lock, coalesced_sync, is_duplicate_callback
from handlers.game_flow import sync_board_message

logger = logging.getLogger(__name__)

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


async def _sync_and_save(
    bot: Bot, db_conn: asyncpg.Pool, game_id: str, move_to_bottom: bool, fresh_game: Game | None
) -> None:
    """رندر/ارسال - عمداً *بیرونِ* قفلِ بازی صدا زده می‌شه، و با coalesced_sync
    محافظت می‌شه. fresh_game اگه داده بشه، بارِ اول (بدونِ رقابت) از همون استفاده
    می‌شه (بدونِ fetch اضافه از دیتابیس)؛ اگه coalescing تشخیص بده اجرای دومی هم
    لازمه، اون اجرا حتماً دوباره از دیتابیس می‌خونه (چون یعنی حالت عوض شده)."""
    state = {"game": fresh_game}

    async def _do_sync() -> None:
        try:
            target = state["game"] if state["game"] is not None else game_id
            await sync_board_message(bot, db_conn, target, move_to_bottom=move_to_bottom)
        except Exception:
            logger.exception("خطا در sync_board_message برای بازی %s", game_id)
        finally:
            state["game"] = None  # اجرای بعدی (اگه لازم بشه) حتماً fresh فچ کنه

    await coalesced_sync(game_id, _do_sync)


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """دکمه‌های تزئینی/غیرقابل‌کلیک - کاری انجام نمی‌دن."""
    await callback.answer()


@router.callback_query(F.data.startswith("board:"))
async def handle_board_callback(
    callback: CallbackQuery, bot: Bot, db_conn: asyncpg.Pool
) -> None:
    if is_duplicate_callback(callback.id):
        # دقیقاً همین تپ قبلاً پردازش شده - بی‌سروصدا نادیده می‌گیریم (نه پیامِ تکراری)
        return

    parts = callback.data.split(":")
    game_id = parts[1]
    action = parts[2]
    user_id = callback.from_user.id

    move_to_bottom: bool | None = None  # اگه None بمونه، یعنی نیازی به sync نیست
    game: Game | None = None

    async with get_game_lock(game_id):
        game = await load_game(db_conn, game_id)
        if game is None:
            await callback.answer("این بازی دیگه وجود نداره.", show_alert=True)
            return

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

            move_to_bottom = (game.status == GameStatus.FINISHED) or (game.current_turn != turn_before)
            await callback.answer(_GUESS_FEEDBACK[color])
            await save_game(db_conn, game)

        elif action == "endturn":
            if not _is_current_operative(game, user_id):
                await callback.answer("نوبت شما نیست یا مامور این تیم نیستید.", show_alert=True)
                return
            try:
                game.end_turn()
            except GameError as e:
                await callback.answer(str(e), show_alert=True)
                return
            move_to_bottom = True
            await callback.answer("نوبت به تیم مقابل منتقل شد.")
            await save_game(db_conn, game)

        elif action == "endguess":
            if not _is_current_operative(game, user_id):
                await callback.answer("نوبت شما نیست یا مامور این تیم نیستید.", show_alert=True)
                return
            try:
                game.end_guessing()
            except GameError as e:
                await callback.answer(str(e), show_alert=True)
                return
            move_to_bottom = True
            await callback.answer("نوبت به تیم مقابل منتقل شد.")
            await save_game(db_conn, game)

        elif action == "movebottom":
            if user_id != game.host_id:
                await callback.answer("فقط سازنده‌ی بازی می‌تونه پنل رو جابه‌جا کنه.", show_alert=True)
                return
            move_to_bottom = True
            await callback.answer("پنل به آخرین پیام منتقل شد.")

        else:
            await callback.answer()
            return

    # --- قفل اینجا آزاد شده - رندر/ارسالِ سنگین بیرونِ قفل انجام می‌شه ---
    if move_to_bottom is not None:
        await _sync_and_save(bot, db_conn, game_id, move_to_bottom=move_to_bottom, fresh_game=game)


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
    game_id = game.game_id
    fresh_game: Game | None = None

    async with get_game_lock(game_id):
        # بعدِ گرفتنِ قفل، دوباره تازه‌ترین حالت رو می‌خونیم (ممکنه بینِ چک بالا و
        # اینجا یه اکشنِ دیگه حالت رو عوض کرده باشه)
        game = await load_game(db_conn, game_id)
        if game is None or game.status != GameStatus.AWAITING_CLUE:
            return
        try:
            game.set_clue_count(n, word, stars)
        except GameError as e:
            await message.reply(str(e))
            return

        star_note = "*" * stars
        # اول تأییدِ فوری برای جاسوس، بعد کارِ سنگینِ رندر/ارسال
        await message.reply(f"✅ سرنخ ثبت شد: «{word}{star_note}» ({n}) — نوبت حدس‌زدنه!")
        await save_game(db_conn, game)
        fresh_game = game

    if fresh_game is not None:
        await _sync_and_save(bot, db_conn, game_id, move_to_bottom=False, fresh_game=fresh_game)
