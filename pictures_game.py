"""
pictures_game.py
ماژول اختصاصی Codenames Pictures هماهنگ با Aiogram 3
"""

import os
import glob
import random
from io import BytesIO
from typing import List, Tuple, Optional, Dict

from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    InputMediaPhoto,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

TOTAL_PICTURES = 20
COLS = 5
ROWS = 4

ROLE_STARTER_AGENT = "STARTER_AGENT"
ROLE_SECOND_AGENT = "SECOND_AGENT"
ROLE_BYSTANDER = "BYSTANDER"
ROLE_ASSASSIN = "ASSASSIN"

TEAM_RED = "RED"
TEAM_BLUE = "BLUE"

COLOR_MAP = {
    TEAM_RED: (220, 53, 69),
    TEAM_BLUE: (30, 144, 255),
    ROLE_BYSTANDER: (218, 165, 32),
    ROLE_ASSASSIN: (25, 25, 25),
}

# نگهداری بازی‌های فعال گروه‌ها
active_picture_games: Dict[int, "PicturesGameSession"] = {}


class PictureCard:
    def __init__(self, index: int, image_path: str, role: str, team: Optional[str] = None):
        self.index = index
        self.image_path = image_path
        self.role = role
        self.team = team
        self.revealed = False


class PicturesGameSession:
    def __init__(self, pictures_dir: str):
        self.pictures_dir = pictures_dir
        self.starter_team = random.choice([TEAM_RED, TEAM_BLUE])
        self.second_team = TEAM_BLUE if self.starter_team == TEAM_RED else TEAM_RED

        self.current_turn = self.starter_team
        self.starter_remaining = 8
        self.second_remaining = 7

        self.cards: List[PictureCard] = []
        self._initialize_board()

    def _initialize_board(self):
        valid_exts = ("*.webp", "*.png", "*.jpg", "*.jpeg")
        all_images = []
        for ext in valid_exts:
            all_images.extend(glob.glob(os.path.join(self.pictures_dir, ext)))

        if len(all_images) < TOTAL_PICTURES:
            raise ValueError(f"تصاویر کافی در {self.pictures_dir} پیدا نشد! حداقل به ۲۰ تصویر نیاز است.")

        selected_images = random.sample(all_images, TOTAL_PICTURES)

        roles = (
            [ROLE_STARTER_AGENT] * 8 +
            [ROLE_SECOND_AGENT] * 7 +
            [ROLE_BYSTANDER] * 4 +
            [ROLE_ASSASSIN] * 1
        )
        random.shuffle(roles)

        for i in range(TOTAL_PICTURES):
            role = roles[i]
            assigned_team = None
            if role == ROLE_STARTER_AGENT:
                assigned_team = self.starter_team
            elif role == ROLE_SECOND_AGENT:
                assigned_team = self.second_team

            self.cards.append(
                PictureCard(
                    index=i + 1,
                    image_path=selected_images[i],
                    role=role,
                    team=assigned_team
                )
            )

    def reveal_card(self, index: int) -> Tuple[bool, PictureCard, Optional[str]]:
        card = self.cards[index - 1]
        if card.revealed:
            return True, card, None

        card.revealed = True

        if card.role == ROLE_ASSASSIN:
            winner = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED
            return False, card, winner

        if card.team == self.current_turn:
            if self.current_turn == self.starter_team:
                self.starter_remaining -= 1
            else:
                self.second_remaining -= 1

            if self.starter_remaining == 0:
                return False, card, self.starter_team
            if self.second_remaining == 0:
                return False, card, self.second_team

            return True, card, None

        elif card.team is not None and card.team != self.current_turn:
            if card.team == self.starter_team:
                self.starter_remaining -= 1
            else:
                self.second_remaining -= 1

            self.switch_turn()

            if self.starter_remaining == 0:
                return False, card, self.starter_team
            if self.second_remaining == 0:
                return False, card, self.second_team

            return True, card, None
        else:
            self.switch_turn()
            return True, card, None

    def switch_turn(self):
        self.current_turn = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED


class PicturesRenderer:
    @staticmethod
    def render_board(game: PicturesGameSession, is_spymaster: bool = False, thumb_size: int = 240) -> Image.Image:
        card_w, card_h = thumb_size, thumb_size
        padding = 12
        margin = 18

        board_w = (COLS * card_w) + ((COLS - 1) * padding) + (2 * margin)
        board_h = (ROWS * card_h) + ((ROWS - 1) * padding) + (2 * margin)

        board = Image.new("RGBA", (board_w, board_h), (24, 25, 28, 255))
        draw = ImageDraw.Draw(board)

        font = None
        for f in ["arialbd.ttf", "DejaVuSans-Bold.ttf", "arial.ttf", "DejaVuSans.ttf"]:
            try:
                font = ImageFont.truetype(f, 24)
                break
            except Exception:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size=24)
            except Exception:
                font = ImageFont.load_default()

        for idx, card in enumerate(game.cards):
            r = idx // COLS
            c = idx % COLS
            x = margin + c * (card_w + padding)
            y = margin + r * (card_h + padding)

            try:
                with Image.open(card.image_path) as img:
                    card_img = img.convert("RGBA").resize((card_w, card_h), Image.Resampling.LANCZOS)
            except Exception:
                card_img = Image.new("RGBA", (card_w, card_h), (60, 60, 60, 255))

            overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            card_color = COLOR_MAP[card.team] if card.team else COLOR_MAP[card.role]

            if card.revealed:
                overlay_draw.rectangle([0, 0, card_w, card_h], fill=(*card_color, 165))
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=card_color, width=5)
            elif is_spymaster:
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=card_color, width=7)
                overlay_draw.ellipse([card_w - 38, 10, card_w - 10, 38], fill=(*card_color, 245))
                overlay_draw.ellipse([card_w - 38, 10, card_w - 10, 38], outline=(255, 255, 255), width=2)
            else:
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(100, 100, 100, 200), width=2)

            # پلاک شماره کارت (بالا چپ با کادر سفید و شماره کاملاً خوانا)
            badge_w, badge_h = 44, 36
            badge_box = [8, 8, 8 + badge_w, 8 + badge_h]
            overlay_draw.rounded_rectangle(badge_box, radius=8, fill=(10, 10, 10, 230), outline=(255, 255, 255, 220), width=1)

            num_str = str(card.index)
            tx = 18 if len(num_str) == 1 else 10
            overlay_draw.text((tx, 12), num_str, fill=(255, 255, 255), font=font)

            card_composite = Image.alpha_composite(card_img, overlay)
            board.paste(card_composite, (x, y))

        return board.convert("RGB")


def build_keyboard(game: PicturesGameSession) -> InlineKeyboardMarkup:
    buttons = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            idx = r * COLS + c
            card = game.cards[idx]
            if card.revealed:
                if card.role == ROLE_ASSASSIN:
                    text = f"💀 {card.index}"
                elif card.role == ROLE_BYSTANDER:
                    text = f"⬜️ {card.index}"
                elif card.team == TEAM_RED:
                    text = f"🟥 {card.index}"
                else:
                    text = f"🟦 {card.index}"
                row.append(InlineKeyboardButton(text=text, callback_data="pic_noop"))
            else:
                row.append(InlineKeyboardButton(text=str(card.index), callback_data=f"pic_guess_{card.index}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="⏭ پایان نوبت (Pass)", callback_data="pic_pass")])
    buttons.append([InlineKeyboardButton(text="🕵️‍♂️ نقشه کلید (مخصوص اسپای‌مستر)", callback_data="pic_spymaster")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================================
# روتر و هندلرهای Aiogram 3
# ==========================================
pictures_router = Router(name="pictures_router")


def _get_caption(game: PicturesGameSession, extra: str = "") -> str:
    turn_fa = "تیم قرمز 🔴" if game.current_turn == TEAM_RED else "تیم آبی 🔵"
    red_rem = game.starter_remaining if game.starter_team == TEAM_RED else game.second_remaining
    blue_rem = game.starter_remaining if game.starter_team == TEAM_BLUE else game.second_remaining

    text = (
        f"🖼 **بازی Codenames: Pictures**\n"
        f"👑 نوبت فعلی: **{turn_fa}**\n\n"
        f"🔴 اهداف باقی‌مانده قرمز: **{red_rem}**\n"
        f"🔵 اهداف باقی‌مانده آبی: **{blue_rem}**\n\n"
        f"شماره کارت مورد نظر را از دکمه‌های زیر انتخاب کنید:"
    )
    if extra:
        text = f"{extra}\n\n" + text
    return text


@pictures_router.message(Command("pictures", "codenames_pictures"))
async def start_pictures_game(message: Message):
    chat_id = message.chat.id
    pictures_path = os.path.join(os.getcwd(), "assets", "pictures")

    try:
        game = PicturesGameSession(pictures_dir=pictures_path)
    except Exception as e:
        await message.reply(f"❌ خطا در شروع بازی تصویری: {e}")
        return

    active_picture_games[chat_id] = game

    img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio = BytesIO()
    img.save(bio, format="JPEG", quality=90)
    bio.seek(0)

    photo_file = BufferedInputFile(bio.getvalue(), filename="board.jpg")
    await message.answer_photo(
        photo=photo_file,
        caption=_get_caption(game),
        reply_markup=build_keyboard(game),
        parse_mode="Markdown"
    )


@pictures_router.callback_query(F.data.startswith("pic_guess_"))
async def on_guess_card(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_picture_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی پیدا نشد. یک بازی جدید شروع کنید.", show_alert=True)
        return

    card_idx = int(callback.data.split("_")[2])
    card = game.cards[card_idx - 1]

    if card.revealed:
        await callback.answer("این کارت قبلاً باز شده است.", show_alert=False)
        return

    await callback.answer()
    is_continue, card, winner = game.reveal_card(card_idx)

    extra_msg = ""
    if winner:
        winner_fa = "تیم قرمز 🔴" if winner == TEAM_RED else "تیم آبی 🔵"
        extra_msg = f"🏆 **پایان بازی! {winner_fa} برنده مسابقه شد!**"
        active_picture_games.pop(chat_id, None)

    img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio = BytesIO()
    img.save(bio, format="JPEG", quality=90)
    bio.seek(0)

    media = InputMediaPhoto(
        media=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
        caption=_get_caption(game, extra=extra_msg),
        parse_mode="Markdown"
    )

    try:
        await callback.message.edit_media(media=media, reply_markup=build_keyboard(game))
    except Exception:
        pass


@pictures_router.callback_query(F.data == "pic_pass")
async def on_pass_turn(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_picture_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی پیدا نشد.", show_alert=True)
        return

    game.switch_turn()
    await callback.answer("نوبت واگذار شد.")

    img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio = BytesIO()
    img.save(bio, format="JPEG", quality=90)
    bio.seek(0)

    media = InputMediaPhoto(
        media=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
        caption=_get_caption(game, extra="⏭ نوبت توسط تیم واگذار شد."),
        parse_mode="Markdown"
    )
    try:
        await callback.message.edit_media(media=media, reply_markup=build_keyboard(game))
    except Exception:
        pass


@pictures_router.callback_query(F.data == "pic_spymaster")
async def on_spymaster_key(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = active_picture_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی یافت نشد.", show_alert=True)
        return

    img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio = BytesIO()
    img.save(bio, format="JPEG", quality=90)
    bio.seek(0)

    key_file = BufferedInputFile(bio.getvalue(), filename="spymaster_key.jpg")
    try:
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=key_file,
            caption="🗺 **نقشه کلید Codenames Pictures (مخصوص اسپای‌مستر)**\nاین تصویر را به هم‌تیمی‌های خود نشان ندهید!"
        )
        await callback.answer("نقشه کلید کارت‌ها به پی‌وی شما ارسال شد!", show_alert=True)
    except Exception:
        await callback.answer("خطا! لطفاً ابتدا به پی‌وی ربات رفته و دکمه Start را بزنید تا ربات اجازه ارسال پیام را داشته باشد.", show_alert=True)


@pictures_router.callback_query(F.data == "pic_noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer("این تصویر قبلاً باز شده است.", show_alert=False)


# ==========================================
# تزریق هوشمند و خودکار به حالت اینلاین
# بدون دستکاری فایل‌های دیگر پروژه
# ==========================================
_orig_inline_answer = InlineQuery.answer

async def _patched_inline_answer(self, *args, **kwargs):
    try:
        results = kwargs.get("results")
        is_kw = True
        if results is None and len(args) > 0:
            results = args[0]
            is_kw = False

        if isinstance(results, (list, tuple)):
            results_list = list(results)
            if not any(getattr(r, "id", None) == "mode_pictures" for r in results_list):
                pic_item = InlineQueryResultArticle(
                    id="mode_pictures",
                    title="🖼 کدنیمز تصویری (Codenames: Pictures)",
                    description="بازی با ۲۰ کارت تصویری در شبکه ۵×۴ با قوانین رسمی",
                    input_message_content=InputTextMessageContent(
                        message_text="/pictures"
                    )
                )
                results_list.append(pic_item)
                if is_kw:
                    kwargs["results"] = results_list
                else:
                    args = (results_list,) + args[1:]
    except Exception:
        pass
    return await _orig_inline_answer(self, *args, **kwargs)

InlineQuery.answer = _patched_inline_answer
