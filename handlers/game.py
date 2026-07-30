"""
هندلرهای حین بازی: کلیک روی کلمه (حدس)، پایان دست، اتمام حدس،
و پردازش ریپلای متنی جاسوس روی پیام پنل بازی (عدد + کلمه‌ی سرنخ).

سه نکته‌ی مهمِ کارایی/صحت:

۱) callback.answer() بلافاصله بعدِ اعتبارسنجی و اعمالِ منطقِ بازی صدا زده می‌شه -
   قبل از رندر/ارسالِ سنگینِ عکس.

۲) قفلِ per-game (game/locks.py) فقط دورِ بخشِ *سریع* (load -> تغییر -> answer -> save)
   کشیده می‌شه - نه دورِ رندر/آپلودِ عکس. اگه قفل دورِ کلِ فرآیند (شاملِ رندر/آپلود که
   خودش چند ثانیه طول می‌کشه) کشیده بشه، هر اکشنِ بعدیِ روی همون بازی باید کاملاً
   منتظرِ تمومِ اون فرآیندِ کند بمونه - حتی برای صدازدنِ خودِ callback.answer()! دقیقاً
   همین باعث شد توی لاگِ واقعیِ سرور، بعضی اکشن‌ها ۴۰+ ثانیه طول بکشن و تلگرام
   کوئریِ callback رو "too old" اعلام کنه (چون callback query هم باید سریع جواب داده
   بشه). الان قفل خیلی زود آزاد می‌شه، رندر/ارسال بیرونِ قفل انجام می‌شه.

۳) چون رندر بیرونِ قفل انجام می‌شه، ممکنه بینِ آزادشدنِ قفل و انجام‌شدنِ رندر، یه
   اکشنِ دیگه حالت رو عوض کرده باشه. برای همین sync_board_message به‌جای گرفتنِ
   آبجکتِ game، فقط game_id می‌گیره و خودش همون‌موقع آخرین حالت رو از دیتابیس
   می‌خونه - این‌طوری همیشه جدیدترین حالت رندر می‌شه، نه یه نسخه‌ی قدیمی.
"""
from __future__ import annotations

import logging

import asyncpg
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message

from database.repository import save_game, load_game, load_active_game_by_chat
from game.state import GameError, GameStatus, Role, CardColor
from game.clue_parser import parse_clue
from game.locks import get_game_lock, coalesced_sync
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


async def _sync_and_save(bot: Bot, db_conn: asyncpg.Pool, game_id: str, move_to_bottom: bool) -> None:
    """رندر/ارسال - عمداً *بیرونِ* قفلِ بازی صدا زده می‌شه (نکته‌ی ۲ بالای فایل)، و با
    coalesced_sync محافظت می‌شه تا اگه چندتا اکشنِ پشتِ‌سرِهم صدا زده باشنش، بیش از
    یه sync هم‌زمان روی همین بازی اجرا نشه (وگرنه چندتا عکسِ اضافه/اسپم می‌شه).
    خطای احتمالیِ اینجا (معمولاً شبکه‌ای/موقتی) فقط لاگ می‌شه، نه اینکه کرش کنه."""

    async def _do_sync() -> None:
        try:
            await sync_board_message(bot, db_conn, game_id, move_to_bottom=move_to_bottom)
        except Exception:
            logger.exception("خطا در sync_board_message برای بازی %s", game_id)

    await coalesced_sync(game_id, _do_sync)


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
    user_id = callback.from_user.id

    move_to_bottom: bool | None = None  # اگه None بمونه، یعنی نیازی به sync نیست

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
        await _sync_and_save(bot, db_conn, game_id, move_to_bottom=move_to_bottom)


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
    success = False

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
        success = True

    if success:
        await _sync_and_save(bot, db_conn, game_id, move_to_bottom=False)
