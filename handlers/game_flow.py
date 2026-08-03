"""
منطق مشترک بین لابی و بازی - نسخه‌ی نهایی با تولید واقعی عکس (Pillow):
- begin_game: تبدیل لابی به پنل بازیِ عکسی + فرستادن عکس خصوصی رنگی به هر جاسوس
- sync_board_message: بعد از هر اکشن، عکس گروه رو آپدیت می‌کنه (ادیت یا حذف+ارسال)
  و عکس خصوصی جاسوس‌ها رو هم (فقط ضربدرها) به‌روز می‌کنه

نکته‌ی مهمِ کارایی: رندرِ Pillow و انکودِ PNG کاملاً CPU-bound و synchronous هستن (هیچ
await داخلی ندارن). اگه مستقیم داخلِ یه تابعِ async صدا زده بشن، کلِ event loop رو
برای مدتِ رندر (چندصد میلی‌ثانیه تا چند ثانیه) کاملاً می‌بندن - یعنی هیچ بازیِ دیگه‌ای
توی هیچ گروهِ دیگه‌ای هم نمی‌تونه پردازش بشه. توی یه بازیِ فعال با کلیک‌های پی‌درپی،
این تأخیرها روی هم جمع می‌شن و دقیقاً همون کندی/فریزِ کاملی که گزارش شده رو می‌سازن.
راه‌حل: هر رندر+انکود رو با asyncio.to_thread می‌بریم به یه ترد جدا، تا event loop
اصلی همیشه آزاد بمونه و بتونه هم‌زمان به بقیه‌ی بازی‌ها/گروه‌ها هم جواب بده.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os

import asyncpg
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto, FSInputFile, Message
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from PIL import Image

from database.repository import save_game, load_game
from game.state import Game, Team, Role, GameStatus
from keyboards.board import build_board_rows, build_board_caption
from keyboards.types import to_aiogram_markup
from imaging.board_renderer import render_board, render_spymaster_board

logger = logging.getLogger(__name__)


_lobby_banner_index = 0


def _pick_lobby_banner_path() -> str | None:
    """عکسِ بعدی رو به‌ترتیب (نه رندوم) از لیستِ LOBBY_BANNER_PATHS انتخاب می‌کنه.
    فقط بینِ فایل‌هایی که واقعاً روی دیسک هستن می‌چرخه (بقیه رو نادیده می‌گیره)."""
    global _lobby_banner_index
    from config import LOBBY_BANNER_PATHS

    existing = [p for p in LOBBY_BANNER_PATHS if os.path.exists(p)]
    if not existing:
        return None
    path = existing[_lobby_banner_index % len(existing)]
    _lobby_banner_index += 1
    return path


async def send_lobby_message(bot: Bot, chat_id: int, caption: str, reply_markup) -> Message:
    """
    پیامِ لابی رو با یکی از عکس‌های بنر (به‌ترتیب، نه رندوم - config.LOBBY_BANNER_PATHS)
    می‌فرسته. اگه هیچ فایلی هنوز روی سرور آپلود نشده باشه، به‌جای کرش‌کردن، خودکار به
    پیامِ متنیِ ساده (بدونِ عکس) fallback می‌کنه - بازی همچنان کار می‌کنه.
    """
    banner_path = _pick_lobby_banner_path()

    if banner_path:
        try:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(banner_path),
                caption=caption,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("خطا در فرستادنِ عکسِ بنرِ لابی - fallback به متنِ ساده")

    return await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)


_OUTPUT_SCALE = 0.8  # کوچیک‌کردنِ عکسِ نهایی قبل از انکود - حجم/زمانِ آپلود رو محسوس
                     # کم می‌کنه، بدونِ افتِ محسوسِ خوانایی (متن‌ها بولد و supersample شدن)


def _downscale_for_output(img):
    if _OUTPUT_SCALE >= 1.0:
        return img
    new_size = (round(img.width * _OUTPUT_SCALE), round(img.height * _OUTPUT_SCALE))
    return img.resize(new_size, Image.LANCZOS)


def _render_group_image_bytes(render_kwargs: dict) -> bytes:
    """رندر + انکودِ پنلِ گروه. خروجی JPEG (نه PNG) با کیفیتِ ۸۸ و کوچیک‌شده به ۸۰٪:
    طبقِ اندازه‌گیری، حجم رو در مجموع ~۵۰٪ کم می‌کنه (آپلود/ادیت روی تلگرام سریع‌تر
    می‌شه) با افتِ کیفیتِ قابلِ قبول."""
    img = render_board(**render_kwargs).convert("RGB")
    img = _downscale_for_output(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=87, optimize=True)
    return buf.getvalue()


def _render_spymaster_image_bytes(spymaster_cards: list[dict]) -> bytes:
    """رندر + انکودِ نقشه‌ی جاسوس (همون منطقِ بالا)."""
    img = render_spymaster_board(spymaster_cards).convert("RGB")
    img = _downscale_for_output(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=87, optimize=True)
    return buf.getvalue()


def _bytes_to_input_file(data: bytes, filename: str = "board.jpg") -> BufferedInputFile:
    return BufferedInputFile(data, filename=filename)


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
        sm_png = await asyncio.to_thread(_render_spymaster_image_bytes, spymaster_cards)
        try:
            msg = await bot.send_photo(
                chat_id=user_id,
                photo=_bytes_to_input_file(sm_png),
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
    spymaster_cards = _build_spymaster_cards(game)

    # رندرِ عکسِ گروه و عکسِ جاسوس هم‌زمان (روی دو ترد جدا)
    group_png, sm_png = await asyncio.gather(
        asyncio.to_thread(_render_group_image_bytes, render_kwargs),
        asyncio.to_thread(_render_spymaster_image_bytes, spymaster_cards),
    )
    caption = build_board_caption(game)
    markup = to_aiogram_markup(build_board_rows(game, Role.OPERATIVE))

    try:
        sent = await bot.send_photo(
            chat_id=game.chat_id,
            photo=_bytes_to_input_file(group_png),
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

    # --- عکس خصوصیِ رنگیِ جاسوس‌ها (رندر بالا مشترکه، برای همه‌شون یکسانه) ---
    spymasters = [p for p in game.players.values() if p.role == Role.SPYMASTER]
    failed_names: list[str] = []

    for sm in spymasters:
        try:
            msg = await bot.send_photo(
                chat_id=sm.user_id,
                photo=_bytes_to_input_file(sm_png),
                caption=f"🕵️ نقشه‌ی کامل بازی (تیم {sm.team.value})",
                protect_content=True,
            )
            game.spymaster_message_ids[str(sm.user_id)] = msg.message_id
        except TelegramForbiddenError:
            failed_names.append(sm.name)
            asyncio.create_task(
                _wait_and_send_spymaster_photo(bot, conn, game.game_id, sm.user_id, sm.team.value)
            )
        except Exception:
            # هر خطای دیگه (شبکه/timeout/rate-limit و...) - این‌طوری اگه یه جاسوس
            # مشکل داشت، بقیه‌ی جاسوس‌ها بی‌نصیب نمی‌مونن (باگِ قبلی دقیقاً همین بود:
            # فقط TelegramForbiddenError گرفته می‌شد و بقیه‌ی خطاها کلِ حلقه رو می‌بستن)
            logger.exception(
                "خطا در فرستادنِ عکسِ جاسوس به %s (game=%s)", sm.user_id, game.game_id
            )
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
    bot: Bot, conn: asyncpg.Pool, game_or_id, move_to_bottom: bool
) -> None:
    """
    بعد از هر اکشن (حدس/پایان دست/اتمام حدس):
    - عکس گروه (پنل بازی) رو آپدیت می‌کنه: یا ادیت درجا، یا حذف+ارسال ته چت
    - عکس خصوصیِ هر جاسوس رو هم (با ضربدرهای جدید روی کارت‌های حدس‌زده‌شده) ادیت می‌کنه
    هر دو رندر با asyncio.to_thread روی یه ترد جدا انجام می‌شن تا بازی‌های دیگه معطل نمونن،
    و ارسال/ادیتِ پیام‌های جاسوس‌ها هم موازی (asyncio.gather) انجام می‌شه تا سریع‌تر باشه.

    game_or_id: یا خودِ آبجکتِ Game (مثلاً از begin_game که تازه ساخته شده)، یا رشته‌ی
    game_id. اگه game_id داده بشه، همینجا آخرین حالت رو از دیتابیس می‌خونیم - چون این
    تابع می‌تونه بعد از آزادشدنِ قفلِ بازی صدا زده بشه (برای اینکه رندر/آپلودِ سنگین
    بقیه‌ی اکشن‌های همون بازی رو معطل نکنه)، و توی اون فاصله ممکنه یه اکشنِ دیگه
    حالتِ بازی رو عوض کرده باشه؛ رندر باید همیشه روی *جدیدترین* حالت انجام بشه، نه
    یه نسخه‌ی احتمالاً قدیمی که موقعِ گرفتنِ قفل توی حافظه بود.
    """
    if isinstance(game_or_id, str):
        game = await load_game(conn, game_or_id)
        if game is None:
            return
    else:
        game = game_or_id

    render_kwargs = _build_group_render_kwargs(game)
    spymaster_cards = _build_spymaster_cards(game)

    # رندرِ عکسِ گروه و عکسِ جاسوس هم‌زمان (روی دو ترد جدا) - نه پشتِ‌سرِهم
    group_png, sm_png = await asyncio.gather(
        asyncio.to_thread(_render_group_image_bytes, render_kwargs),
        asyncio.to_thread(_render_spymaster_image_bytes, spymaster_cards),
    )
    caption = build_board_caption(game)
    markup = to_aiogram_markup(build_board_rows(game, Role.OPERATIVE))

    if not move_to_bottom:
        try:
            media = InputMediaPhoto(media=_bytes_to_input_file(group_png), caption=caption)
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
            photo=_bytes_to_input_file(group_png),
            caption=caption,
            reply_markup=markup,
        )
        game.last_message_id = sent.message_id

    # --- آپدیت عکس خصوصیِ جاسوس‌ها (فقط ضربدرهای جدید) - رندر بالا مشترکه، ارسال موازی ---
    spymasters = [p for p in game.players.values() if p.role == Role.SPYMASTER]

    async def _update_one_spymaster(sm) -> None:
        msg_id = game.spymaster_message_ids.get(str(sm.user_id))
        if msg_id is None:
            return
        try:
            media = InputMediaPhoto(media=_bytes_to_input_file(sm_png))
            await bot.edit_message_media(chat_id=sm.user_id, message_id=msg_id, media=media)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        except Exception:
            logger.exception(
                "خطا در آپدیتِ عکسِ جاسوس برای %s (game=%s)", sm.user_id, game.game_id
            )

    await asyncio.gather(*(_update_one_spymaster(sm) for sm in spymasters))

    await save_game(conn, game)
