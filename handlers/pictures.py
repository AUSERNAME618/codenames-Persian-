"""
handlers/pictures.py
ماژول اختصاصی Codenames: Pictures
- لابی استاندارد با بنر، نقش‌های جاسوس‌ارشد و مامور و شرط حداقل ۴ بازیکن
- ارسال خودکار نقشه به پی‌وی جاسوس‌ها در شروع مسابقه با protect_content و بدون متن
- آپدیت زنده و بی‌صدای نقشه در پی‌وی جاسوس‌ها پس از هر حدس
- شبکه ۵×۴ با پلاک دایره‌ای تراز شده و اورلی کامل رنگی (قرمز، آبی، کرمی خاکی، مشکی)
"""

import os
import glob
import random
import logging
from io import BytesIO
from typing import List, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    InputMediaPhoto,
    FSInputFile,
)

logger = logging.getLogger("codenames_bot.pictures")

router = Router(name="pictures_game")

TOTAL_PICTURES = 20
COLS = 5
ROWS = 4

ROLE_STARTER_AGENT = "STARTER_AGENT"
ROLE_SECOND_AGENT = "SECOND_AGENT"
ROLE_BYSTANDER = "BYSTANDER"
ROLE_ASSASSIN = "ASSASSIN"

TEAM_RED = "RED"
TEAM_BLUE = "BLUE"

# پالت رنگی مورد نظر: قرمز، آبی، کرمی خاکی، مشکی
COLOR_MAP = {
    TEAM_RED: (220, 50, 50),
    TEAM_BLUE: (35, 125, 235),
    ROLE_BYSTANDER: (210, 190, 155),
    ROLE_ASSASSIN: (20, 20, 25),
}

pic_lobbies: Dict[int, Dict] = {}
pic_games: Dict[int, "PicturesGameSession"] = {}


class PictureCard:
    def __init__(self, index: int, image_path: str, role: str, team: Optional[str] = None):
        self.index = index
        self.image_path = image_path
        self.role = role
        self.team = team
        self.revealed = False


class PicturesGameSession:
    def __init__(self, pictures_dir: str, red_spymaster: dict, blue_spymaster: dict, red_operatives: dict, blue_operatives: dict):
        self.pictures_dir = pictures_dir
        self.red_spymaster = red_spymaster
        self.blue_spymaster = blue_spymaster
        self.red_operatives = red_operatives
        self.blue_operatives = blue_operatives

        self.starter_team = random.choice([TEAM_RED, TEAM_BLUE])
        self.second_team = TEAM_BLUE if self.starter_team == TEAM_RED else TEAM_RED

        self.current_turn = self.starter_team
        self.starter_remaining = 8
        self.second_remaining = 7

        self.spymaster_msg_ids: Dict[int, int] = {}
        self.cards: List[PictureCard] = []
        self._initialize_board()

    def _initialize_board(self):
        valid_exts = ("*.webp", "*.png", "*.jpg", "*.jpeg")
        all_images = []
        for ext in valid_exts:
            all_images.extend(glob.glob(os.path.join(self.pictures_dir, ext)))

        if len(all_images) < TOTAL_PICTURES:
            raise ValueError(f"حداقل ۲۰ تصویر در پوشه {self.pictures_dir} پیدا نشد!")

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
        padding = 14
        margin = 20

        board_w = (COLS * card_w) + ((COLS - 1) * padding) + (2 * margin)
        board_h = (ROWS * card_h) + ((ROWS - 1) * padding) + (2 * margin)

        board = Image.new("RGBA", (board_w, board_h), (20, 22, 26, 255))

        # استفاده از فونت اختصاصی پفک برای ارقام
        font = None
        font_files = [
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-ExtraBold.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-DemiBold.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-Medium.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-_Regular.ttf"),
            "arialbd.ttf",
            "DejaVuSans-Bold.ttf"
        ]
        for f in font_files:
            if os.path.exists(f) or not f.endswith(".ttf"):
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
                # اورلی یکدست و کامل روی کارت انتخاب‌شده
                overlay_draw.rectangle([0, 0, card_w, card_h], fill=(*card_color, 175))
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(*card_color, 255), width=5)
            elif is_spymaster:
                # دید اسپای‌مستر: اورلی ملایم با حاشیه ضخیم
                overlay_draw.rectangle([0, 0, card_w, card_h], fill=(*card_color, 105))
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(*card_color, 255), width=7)
            else:
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(75, 80, 90, 220), width=2)

            # دایره پلاک شماره در گوشه چپ کارت
            badge_r = 18
            badge_cx = 28
            badge_cy = 28

            overlay_draw.ellipse(
                [badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r],
                fill=(12, 14, 18, 240),
                outline=(255, 255, 255, 230),
                width=2
            )

            # محاسبه دقیق مرکز متن بدون کج شدن
            num_str = str(card.index)
            bbox = font.getbbox(num_str)
            tx = badge_cx - (bbox[0] + bbox[2]) / 2
            ty = badge_cy - (bbox[1] + bbox[3]) / 2
            overlay_draw.text((tx, ty), num_str, fill=(255, 255, 255, 255), font=font)

            card_composite = Image.alpha_composite(card_img, overlay)
            board.paste(card_composite, (x, y))

        return board.convert("RGB")


# ==========================================
# کیبوردها
# ==========================================

def build_lobby_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 جاسوس‌ارشد", callback_data="pic_sm_red"),
            InlineKeyboardButton(text="🔵 جاسوس‌ارشد", callback_data="pic_sm_blue")
        ],
        [
            InlineKeyboardButton(text="🔴 مامور", callback_data="pic_op_red"),
            InlineKeyboardButton(text="🔵 مامور", callback_data="pic_op_blue")
        ],
        [
            InlineKeyboardButton(text="🎲 عضویت تصادفی", callback_data="pic_random"),
            InlineKeyboardButton(text="🚪 خروج از تیم", callback_data="pic_leave")
        ],
        [
            InlineKeyboardButton(text="🚀 شروع بازی", callback_data="pic_start_game"),
            InlineKeyboardButton(text="❌ لغو لابی", callback_data="pic_cancel_lobby")
        ]
    ])


def build_game_keyboard(game: PicturesGameSession) -> InlineKeyboardMarkup:
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
                row.append(InlineKeyboardButton(text=f" {card.index} ", callback_data=f"pic_guess_{card.index}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="⏭ پایان نوبت (Pass)", callback_data="pic_pass")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_lobby_text(lobby: dict) -> str:
    red_sm = lobby["red_spymaster"]["name"] if lobby["red_spymaster"] else "❌ تعیین نشده"
    blue_sm = lobby["blue_spymaster"]["name"] if lobby["blue_spymaster"] else "❌ تعیین نشده"

    red_ops = ", ".join(lobby["red_operatives"].values()) if lobby["red_operatives"] else "❌ تعیین نشده"
    blue_ops = ", ".join(lobby["blue_operatives"].values()) if lobby["blue_operatives"] else "❌ تعیین نشده"

    return (
        "🎮 **لابی بازی کدنیمز تصویری (Codenames: Pictures)**\n\n"
        "🔴 **تیم قرمز:**\n"
        f"🕵️‍♂️ جاسوس‌ارشد: **{red_sm}**\n"
        f"👥 ماموران: {red_ops}\n\n"
        "🔵 **تیم آبی:**\n"
        f"🕵️‍♂️️ جاسوس‌ارشد: **{blue_sm}**\n"
        f"👥 ماموران: {blue_ops}\n\n"
        "▫️ ابعاد تخته: ۵ ستون × ۴ ردیف (۲۰ کارت تصویری)\n"
        "▫️ برای شروع مسابقه هر دو تیم باید حداقل یک جاسوس‌ارشد و یک مامور داشته باشند (حداقل ۴ نفر).\n"
        "⚠️ **توجه:** جاسوس‌های ارشد باید قبل از شروع، ربات را در پی‌وی Start کرده باشند."
    )


def _get_game_caption(game: PicturesGameSession, extra: str = "") -> str:
    turn_fa = "تیم قرمز 🔴" if game.current_turn == TEAM_RED else "تیم آبی 🔵"
    red_rem = game.starter_remaining if game.starter_team == TEAM_RED else game.second_remaining
    blue_rem = game.starter_remaining if game.starter_team == TEAM_BLUE else game.second_remaining

    red_sm = game.red_spymaster["name"]
    blue_sm = game.blue_spymaster["name"]

    text = (
        f"🖼 **مسابقه Codenames: Pictures**\n"
        f"👑 نوبت: **{turn_fa}**\n\n"
        f"🔴 اهداف قرمز: **{red_rem}** (جاسوس‌ارشد: {red_sm})\n"
        f"🔵 اهداف آبی: **{blue_rem}** (جاسوس‌ارشد: {blue_sm})\n\n"
        f"نوبت جاسوس‌ارشد {turn_fa} است که سرنخ بدهد.\n"
        f"ماموران برای حدس زدن روی شماره تصویر کلیک کنند:"
    )
    if extra:
        text = f"{extra}\n\n" + text
    return text


async def _update_spymaster_maps(bot: Bot, game: PicturesGameSession):
    """آپدیت بی‌صدا و زنده نقشه در پی‌وی هر دو جاسوس‌‌ارشد بدون ارسال متن"""
    key_img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio = BytesIO()
    key_img.save(bio, format="JPEG", quality=92)
    bio.seek(0)
    bytes_data = bio.getvalue()

    for sm_id in (game.red_spymaster["id"], game.blue_spymaster["id"]):
        msg_id = game.spymaster_msg_ids.get(sm_id)
        media_input = InputMediaPhoto(
            media=BufferedInputFile(bytes_data, filename="spymaster_key.jpg"),
            caption=None
        )
        if msg_id:
            try:
                await bot.edit_message_media(
                    chat_id=sm_id,
                    message_id=msg_id,
                    media=media_input
                )
                continue
            except Exception:
                pass

        try:
            new_msg = await bot.send_photo(
                chat_id=sm_id,
                photo=BufferedInputFile(bytes_data, filename="spymaster_key.jpg"),
                caption=None,
                protect_content=True,
                disable_notification=True
            )
            game.spymaster_msg_ids[sm_id] = new_msg.message_id
        except Exception:
            pass


# ==========================================
# هندلرها
# ==========================================

@router.message(Command("pictures", "codenames_pictures"))
@router.message(F.text.regexp(r"^/codenames\s+pictures$"))
async def start_pictures_lobby_cmd(message: Message):
    chat_id = message.chat.id
    pic_lobbies[chat_id] = {
        "host_id": message.from_user.id,
        "red_spymaster": None,
        "blue_spymaster": None,
        "red_operatives": {},
        "blue_operatives": {},
    }

    # استفاده از بنر موجود در پروژه مشابه نسخه متنی
    banners = [
        os.path.join(os.getcwd(), "assets", "images", f"lobby_banner_{i}.jpg")
        for i in [1, 2, 3]
    ]
    existing = [b for b in banners if os.path.exists(b)]
    banner_file = random.choice(existing) if existing else None

    if banner_file:
        await message.answer_photo(
            photo=FSInputFile(banner_file),
            caption=_get_lobby_text(pic_lobbies[chat_id]),
            reply_markup=build_lobby_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            text=_get_lobby_text(pic_lobbies[chat_id]),
            reply_markup=build_lobby_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(F.data.in_(["pic_sm_red", "pic_sm_blue", "pic_op_red", "pic_op_blue", "pic_random", "pic_leave"]))
async def on_lobby_action(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lobby = pic_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("لابی منقضی شده است. مجدداً دستور /pictures را بزنید.", show_alert=True)
        return

    user = callback.from_user
    uid = user.id
    uname = user.full_name
    action = callback.data

    # خروج از نقش قبلی
    def _remove_user():
        if lobby["red_spymaster"] and lobby["red_spymaster"]["id"] == uid:
            lobby["red_spymaster"] = None
        if lobby["blue_spymaster"] and lobby["blue_spymaster"]["id"] == uid:
            lobby["blue_spymaster"] = None
        lobby["red_operatives"].pop(uid, None)
        lobby["blue_operatives"].pop(uid, None)

    if action == "pic_leave":
        _remove_user()
        await callback.answer("از تیم خارج شدید.")
    elif action == "pic_random":
        _remove_user()
        # عضویت در تیمی که تعداد کمتری مامور دارد
        if len(lobby["red_operatives"]) <= len(lobby["blue_operatives"]):
            lobby["red_operatives"][uid] = uname
            await callback.answer("به ماموران قرمز ملحق شدید!")
        else:
            lobby["blue_operatives"][uid] = uname
            await callback.answer("به ماموران آبی ملحق شدید!")
    elif action == "pic_sm_red":
        if lobby["red_spymaster"] and lobby["red_spymaster"]["id"] != uid:
            await callback.answer("این نقش قبلاً انتخاب شده است.", show_alert=True)
            return
        _remove_user()
        lobby["red_spymaster"] = {"id": uid, "name": uname}
        await callback.answer("به‌عنوان جاسوس‌ارشد قرمز انتخاب شدید!")
    elif action == "pic_sm_blue":
        if lobby["blue_spymaster"] and lobby["blue_spymaster"]["id"] != uid:
            await callback.answer("این نقش قبلاً انتخاب شده است.", show_alert=True)
            return
        _remove_user()
        lobby["blue_spymaster"] = {"id": uid, "name": uname}
        await callback.answer("به‌عنوان جاسوس‌ارشد آبی انتخاب شدید!")
    elif action == "pic_op_red":
        _remove_user()
        lobby["red_operatives"][uid] = uname
        await callback.answer("به ماموران قرمز اضافه شدید!")
    elif action == "pic_op_blue":
        _remove_user()
        lobby["blue_operatives"][uid] = uname
        await callback.answer("به ماموران آبی اضافه شدید!")

    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=_get_lobby_text(lobby),
                reply_markup=build_lobby_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                text=_get_lobby_text(lobby),
                reply_markup=build_lobby_keyboard(),
                parse_mode="Markdown"
            )
    except Exception:
        pass


@router.callback_query(F.data == "pic_cancel_lobby")
async def on_cancel_lobby(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lobby = pic_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("لابی منقضی شده است.", show_alert=True)
        return

    if callback.from_user.id != lobby["host_id"]:
        await callback.answer("فقط ایجادکننده لابی می‌تواند آن را لغو کند.", show_alert=True)
        return

    pic_lobbies.pop(chat_id, None)
    await callback.message.delete()
    await callback.message.answer("❌ لابی مسابقه کدنیمز تصویری لغو شد.")


@router.callback_query(F.data == "pic_start_game")
async def on_start_game(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lobby = pic_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("لابی فعالی پیدا نشد.", show_alert=True)
        return

    if callback.from_user.id != lobby["host_id"]:
        await callback.answer("فقط ایجادکننده لابی می‌تواند بازی را شروع کند.", show_alert=True)
        return

    # بررسی قانون حداقل نفرات (حداقل ۴ نفر)
    if not lobby["red_spymaster"]:
        await callback.answer("تیم قرمز هنوز جاسوس‌ارشد ندارد!", show_alert=True)
        return
    if not lobby["blue_spymaster"]:
        await callback.answer("تیم آبی هنوز جاسوس‌ارشد ندارد!", show_alert=True)
        return
    if len(lobby["red_operatives"]) < 1:
        await callback.answer("تیم قرمز حداقل به یک مامور نیاز دارد!", show_alert=True)
        return
    if len(lobby["blue_operatives"]) < 1:
        await callback.answer("تیم آبی حداقل به یک مامور نیاز دارد!", show_alert=True)
        return

    pictures_path = os.path.join(os.getcwd(), "assets", "pictures")
    try:
        game = PicturesGameSession(
            pictures_dir=pictures_path,
            red_spymaster=lobby["red_spymaster"],
            blue_spymaster=lobby["blue_spymaster"],
            red_operatives=lobby["red_operatives"],
            blue_operatives=lobby["blue_operatives"]
        )
    except Exception as e:
        await callback.answer(f"خطا در ایجاد بازی: {e}", show_alert=True)
        return

    pic_games[chat_id] = game
    pic_lobbies.pop(chat_id, None)

    # رندر نقشه کلید اختصاصی اسپای‌مستر
    key_img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio_key = BytesIO()
    key_img.save(bio_key, format="JPEG", quality=92)
    bio_key.seek(0)
    bytes_key = bio_key.getvalue()

    # ارسال نقشه به پی‌وی هر دو جاسوس‌ارشد با تنظیمات پرایوسی
    failed_pms = []
    for sm in (game.red_spymaster, game.blue_spymaster):
        try:
            msg = await callback.bot.send_photo(
                chat_id=sm["id"],
                photo=BufferedInputFile(bytes_key, filename="spymaster_key.jpg"),
                caption=None,
                protect_content=True,
                disable_notification=True
            )
            game.spymaster_msg_ids[sm["id"]] = msg.message_id
        except Exception:
            failed_pms.append(sm["name"])

    # رندر تخته مسابقه برای گروه
    board_img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio_board = BytesIO()
    board_img.save(bio_board, format="JPEG", quality=92)
    bio_board.seek(0)
    board_file = BufferedInputFile(bio_board.getvalue(), filename="board.jpg")

    extra_warn = ""
    if failed_pms:
        extra_warn = f"⚠️ ربات نتوانست به پی‌وی ({', '.join(failed_pms)}) پیام دهد. لطفاً ابتدا ربات را در پی‌وی استارت کنید."

    await callback.message.delete()
    await callback.message.answer_photo(
        photo=board_file,
        caption=_get_game_caption(game, extra=extra_warn),
        reply_markup=build_game_keyboard(game),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("pic_guess_"))
async def on_guess_card(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = pic_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی پیدا نشد.", show_alert=True)
        return

    uid = callback.from_user.id
    # عدم دسترسی جاسوس‌ارشد به دکمه‌های حدس
    if uid in (game.red_spymaster["id"], game.blue_spymaster["id"]):
        await callback.answer("جاسوس‌ارشد اجازه حدس زدن ندارد!", show_alert=True)
        return

    # بررسی نوبت مامور تیم جاری
    current_team_ops = game.red_operatives if game.current_turn == TEAM_RED else game.blue_operatives
    if uid not in current_team_ops:
        await callback.answer("اکنون نوبت ماموران تیم شما نیست!", show_alert=True)
        return

    card_idx = int(callback.data.split("_")[2])
    card = game.cards[card_idx - 1]

    if card.revealed:
        await callback.answer("این تصویر قبلاً باز شده است.", show_alert=False)
        return

    await callback.answer()
    is_continue, card, winner = game.reveal_card(card_idx)

    extra_msg = ""
    if winner:
        winner_fa = "تیم قرمز 🔴" if winner == TEAM_RED else "تیم آبی 🔵"
        extra_msg = f"🏆 **پایان بازی! {winner_fa} برنده مسابقه شد!**"
        pic_games.pop(chat_id, None)

    # به‌روزرسانی زنده نقشه در پی‌وی جاسوس‌ها
    await _update_spymaster_maps(callback.bot, game)

    # بازتولید تصویر تخته در گروه
    board_img = PicturesRenderer.render_board(game, is_spymaster=(winner is not None))
    bio = BytesIO()
    board_img.save(bio, format="JPEG", quality=92)
    bio.seek(0)

    media = InputMediaPhoto(
        media=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
        caption=_get_game_caption(game, extra=extra_msg),
        parse_mode="Markdown"
    )

    try:
        await callback.message.edit_media(media=media, reply_markup=build_game_keyboard(game))
    except Exception:
        pass


@router.callback_query(F.data == "pic_pass")
async def on_pass_turn(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = pic_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی پیدا نشد.", show_alert=True)
        return

    uid = callback.from_user.id
    current_team_ops = game.red_operatives if game.current_turn == TEAM_RED else game.blue_operatives
    if uid not in current_team_ops:
        await callback.answer("تنها ماموران تیم نوبت اجازه پایان نوبت را دارند.", show_alert=True)
        return

    game.switch_turn()
    await callback.answer("نوبت واگذار شد.")

    # آپدیت پی‌وی جاسوس‌ها
    await _update_spymaster_maps(callback.bot, game)

    board_img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio = BytesIO()
    board_img.save(bio, format="JPEG", quality=92)
    bio.seek(0)

    media = InputMediaPhoto(
        media=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
        caption=_get_game_caption(game, extra="⏭ نوبت واگذار شد."),
        parse_mode="Markdown"
    )
    try:
        await callback.message.edit_media(media=media, reply_markup=build_game_keyboard(game))
    except Exception:
        pass


@router.callback_query(F.data == "pic_noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer("این تصویر قبلاً باز شده است.", show_alert=False)
