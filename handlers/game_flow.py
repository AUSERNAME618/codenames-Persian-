"""
منطق مشترک بین لابی و بازی - نسخه‌ی نهایی با تولید واقعی عکس (Pillow):
- begin_game: تبدیل لابی به پنل بازیِ عکسی + فرستادن عکس خصوصی رنگی به هر جاسوس
- sync_board_message: بعد از هر اکشن، عکس گروه رو آپدیت می‌کنه (ادیت یا حذف+ارسال)
  و عکس خصوصی جاسوس‌ها رو هم (فقط ضربدرها) به‌روز می‌کنه
"""
from __future__ import annotations

import asyncio
import io

import asyncpg
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database.repository import save_game, load_game
from game.state import Game, Team, Role, GameStatus
from keyboards.board import build_board_rows, build_board_caption
from keyboards.types import to_aiogram_markup
from imaging.board_renderer import render_board, render_spymaster_board


def _to_input_file(img, filename: str = "board.png") -> BufferedInputFile:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return BufferedInputFile(buf.read(), filename=filename)


def _names_of(game: Game, team: Team, role: Role) -> list[str]:
    return [p.name for p in game.players.values() if p.team == team and p.role == role]


def _spymaster_name_of(game: Game, team: Team) -> str | None:
    names = _names_of(game, team, Role.SPYMASTER)
    return names[0] if names else None


def _build_group_render_kwargs(game: Game) -> dict:
    """آماده‌سازی ورودی render_board برای دید گروه/مامور (فقط فاش‌شده‌ها رنگی‌ان)."""
    cards = [
        {"word": c.word, "state": (c.color.value if c.revealed else "unrevealed")}
        for c in game.board
    ]

    red_remaining = sum(1 for c in game.board if c.color.value == "red" and not c.revealed)
    blue_remaining = sum(1 for c in game.board if c.color.value == "blue" and not c.revealed)

    winner = game.winner.value if game.winner else None
    winner_players = None
    if game.winner is not None:
        winner_players = [p.name for p in game.players.values() if p.team == game.winner]

    return dict(
        cards=cards,
        current_turn=game.current_turn.value if game.current_turn else "red",
        round_number=game.round_number,
        red_cards_remaining=red_remaining,
        blue_cards_remaining=blue_remaining,
        red_operatives=_names_of(game, Team.RED, Role.OPERATIVE),
        blue_operatives=_names_of(game, Team.BLUE, Role.OPERATIVE),
        red_spymaster=_spymaster_name_of(game, Team.RED),
        blue_spymaster=_spymaster_name_of(game, Team.BLUE),
        red_guess_log=[tuple(x) for x in game.guess_log.get("red", [])],
        blue_guess_log=[tuple(x) for x in game.guess_log.get("blue", [])],
        clue_word=game.clue_word,
        clue_number=(game.clue_count if game.clue_count else None),
        clue_stars=game.clue_stars,
        winner=winner,
        ended_by_assassin=game.ended_by_assassin,
        winner_players=winner_players,
    )


def _build_spymaster_cards(game: Game) -> list[dict]:
    return [
        {
            "word": c.word,
            "state": c.color.value,
            "guessed_by": (c.guessed_by.value if c.guessed_by else None),
        }
        for c in game.board
    ]


async def _wait_and_send_spymaster_photo(
    bot: Bot,
    pool: asyncpg.Pool,
    game_id: str,
    user_id: int,
    team_value: str,
    interval: int = 10,
    max_attempts: int = 180,  # سقفِ ۳۰ دقیقه (۱۸۰ × ۱۰ ثانیه)، فقط برای جلوگیری از حلقه‌ی ابدی
) -> None:
    """
    وقتی فرستادن عکس اولیه‌ی جاسوس به‌خاطر نزدن /start شکست بخوره، این تابع
    (به‌صورت پس‌زمینه، بدون قفل‌کردن بقیه‌ی ربات) هر ۱۰ ثانیه یه‌بار دوباره امتحان می‌کنه.
    هر بار که موفق شد، آخرین وضعیت زنده‌ی بازی رو رندر و می‌فرسته (نه نسخه‌ی قدیمی).
    """
    for _ in range(max_attempts):
        await asyncio.sleep(interval)

        game = await load_game(pool, game_id)
        if game is None or game.status == GameStatus.FINISHED:
            return  # بازی پاک شده یا تموم شده، دیگه لازم نیست تلاش کنیم

        spymaster_cards = _build_spymaster_cards(game)
        sm_img = render_spymaster_board(spymaster_cards)
        try:
            msg = await bot.send_photo(
                chat_id=user_id,
                photo=_to_input_file(sm_img),
                caption=f"🕵️ نقشه‌ی کامل بازی (تیم {team_value})",
                protect_content=True,
            )
        except TelegramForbiddenError:
            continue  # هنوز /start نزده، ۱۰ ثانیه‌ی بعد دوباره
        except Exception:
            continue  # هر خطای موقتی دیگه (مثلاً قطعی شبکه) - دوباره امتحان کن

        game.spymaster_message_ids[str(user_id)] = msg.message_id
        await save_game(pool, game)
        return


async def begin_game(bot: Bot, conn: asyncpg.Pool, game: Game) -> None:
    """
    بعد از start_game(): پیام متنیِ لابی حذف و یه پیامِ عکسیِ جدید (پنل بازی) جایگزینش می‌شه،
    و برای هر جاسوس یه عکسِ خصوصیِ رنگی (یک‌بار، بدون لاگ/پنل) فرستاده می‌شه.
    """
    render_kwargs = _build_group_render_kwargs(game)
    group_img = render_board(**render_kwargs)
    caption = build_board_caption(game)
    markup = to_aiogram_markup(build_board_rows(game, Role.OPERATIVE))

    try:
        sent = await bot.send_photo(
            chat_id=game.chat_id,
            photo=_to_input_file(group_img),
            caption=caption,
            reply_markup=markup,
        )
        try:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.last_message_id)
        except TelegramBadRequest:
            pass
        game.last_message_id = sent.message_id
    except TelegramBadRequest:
        pass

    # --- عکس خصوصیِ رنگیِ جاسوس‌ها (یک‌بار، بدون پنل/لاگ) ---
    spymaster_cards = _build_spymaster_cards(game)
    sm_img = render_spymaster_board(spymaster_cards)
    spymasters = [p for p in game.players.values() if p.role == Role.SPYMASTER]
    failed_names: list[str] = []

    for sm in spymasters:
        try:
            msg = await bot.send_photo(
                chat_id=sm.user_id,
                photo=_to_input_file(sm_img),
                caption=f"🕵️ نقشه‌ی کامل بازی (تیم {sm.team.value})",
                protect_content=True,
            )
            game.spymaster_message_ids[str(sm.user_id)] = msg.message_id
        except TelegramForbiddenError:
            failed_names.append(sm.name)
            asyncio.create_task(
                _wait_and_send_spymaster_photo(bot, conn, game.game_id, sm.user_id, sm.team.value)
            )

    if failed_names:
        names_list = "، ".join(failed_names)
        await bot.send_message(
            chat_id=game.chat_id,
            text=(
                f"⚠️ نتونستم به {names_list} پیام خصوصی بدم. "
                "لطفاً اول یه بار به ربات پیام /start بدید — همین که زدید، خودش نقشه‌ی رنگی رو براتون می‌فرسته."
            ),
        )

    await save_game(conn, game)


async def sync_board_message(
    bot: Bot, conn: asyncpg.Pool, game: Game, move_to_bottom: bool
) -> None:
    """
    بعد از هر اکشن (حدس/پایان دست/اتمام حدس):
    - عکس گروه (پنل بازی) رو آپدیت می‌کنه: یا ادیت درجا، یا حذف+ارسال ته چت
    - عکس خصوصیِ هر جاسوس رو هم (با ضربدرهای جدید روی کارت‌های حدس‌زده‌شده) ادیت می‌کنه
    """
    render_kwargs = _build_group_render_kwargs(game)
    group_img = render_board(**render_kwargs)
    caption = build_board_caption(game)
    markup = to_aiogram_markup(build_board_rows(game, Role.OPERATIVE))

    if not move_to_bottom:
        try:
            media = InputMediaPhoto(media=_to_input_file(group_img), caption=caption)
            await bot.edit_message_media(
                chat_id=game.chat_id,
                message_id=game.last_message_id,
                media=media,
                reply_markup=markup,
            )
        except TelegramBadRequest:
            pass
    else:
        try:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.last_message_id)
        except TelegramBadRequest:
            pass
        sent = await bot.send_photo(
            chat_id=game.chat_id,
            photo=_to_input_file(group_img),
            caption=caption,
            reply_markup=markup,
        )
        game.last_message_id = sent.message_id

    # --- آپدیت عکس خصوصیِ جاسوس‌ها (فقط ضربدرهای جدید) ---
    spymaster_cards = _build_spymaster_cards(game)
    sm_img = render_spymaster_board(spymaster_cards)
    spymasters = [p for p in game.players.values() if p.role == Role.SPYMASTER]

    for sm in spymasters:
        msg_id = game.spymaster_message_ids.get(str(sm.user_id))
        if msg_id is None:
            continue
        try:
            media = InputMediaPhoto(media=_to_input_file(sm_img))
            await bot.edit_message_media(chat_id=sm.user_id, message_id=msg_id, media=media)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass

    await save_game(conn, game)