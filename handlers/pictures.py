"""
handlers/pictures.py
ماژول کامل و مستقل Codenames: Pictures
- لابی مسابقه هماهنگ با سبک اصلی ربات (جاسوس‌ارشد و مامور)
- ارسال ۱۰۰٪ خودکار نقشه به پی‌وی جاسوس‌های ارشد در لحظه شروع بازی
- رندر تخته ۲۰ کارتی (شبکه ۵×۴) با پلاک عددی خوانا (فونت Pofak)
- دکمه‌های عددی ۱ تا ۲۰ متناظر با تصاویر
"""

import os
import glob
import random
import logging
from io import BytesIO
from typing import List, Dict, Optional, Tuple

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

COLOR_MAP = {
    TEAM_RED: (220, 53, 69),
    TEAM_BLUE: (30, 144, 255),
    ROLE_BYSTANDER: (218, 165, 32),
    ROLE_ASSASSIN: (25, 25, 25),
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

        self.cards: List[PictureCard] = []
        self._initialize_board()

    def _initialize_board(self):
        valid_exts = ("*.webp", "*.png", "*.jpg", "*.jpeg")
        all_images = []
        for ext in valid_exts:
            all_images.extend(glob.glob(os.path.join(self.pictures_dir, ext)))

        if len(all_images) < TOTAL_PICTURES:
            raise ValueError(f"حداقل ۲۰ تصویر در مسیر {self.pictures_dir} پیدا نشد!")

        selected_images = random.sample(all_images, TOTAL_PICTURES)

        # تقسیم رسمی نقش‌های نسخه Pictures: 8 + 7 + 4 + 1 = 20
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

        # انتخاب کارت قاتل
        if card.role == ROLE_ASSASSIN:
            winner = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED
            return False, card, winner

        # کارت تیم جاری
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

        # کارت تیم رقیب
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
            # شهروند بی‌طرف
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

        board = Image.new("RGBA", (board_w, board_h), (24, 25, 28, 255))

        # بارگذاری فونت رسمی پروژه Pofak
        font = None
        font_candidates = [
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-ExtraBold.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-DemiBold.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-Medium.ttf"),
            os.path.join(os.getcwd(), "assets", "fonts", "Pofak-_Regular.ttf"),
            "arialbd.ttf",
            "DejaVuSans-Bold.ttf"
        ]
        for f in font_candidates:
            if os.path.exists(f) or not f.endswith(".ttf"):
                try:
                    font = ImageFont.truetype(f, 26)
                    break
                except Exception:
                    continue
        if font is None:
            try:
                font = ImageFont.load_default(size=26)
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
                overlay_draw.ellipse([card_w - 42, 10, card_w - 10, 42], fill=(*card_color, 245))
                overlay_draw.ellipse([card_w - 42, 10, card_w - 10, 42], outline=(255, 255, 255), width=2)
            else:
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(100, 100, 100, 200), width=2)

            # پلاک شماره کارت در گوشه بالا-چپ
            badge_w, badge_h = 46, 38
            badge_box = [8, 8, 8 + badge_w, 8 + badge_h]
            overlay_draw.rounded_rectangle(badge_box, radius=8, fill=(10, 10, 10, 230), outline=(255, 255, 255, 220), width=1)

            num_str = str(card.index)
            tx = 18 if len(num_str) == 1 else 10
            overlay_draw.text((tx, 12), num_str, fill=(255, 255, 255), font=font)

            card_composite = Image.alpha_composite(card_img, overlay)
            board.paste(card_composite, (x, y))

        return board.convert("RGB")


# ==========================================
# دکمه‌های شیشه‌ای
# ==========================================

def build_lobby_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 جاسوس‌ارشد قرمز", callback_data="pic_sm_red"),
            InlineKeyboardButton(text="🔵 جاسوس‌ارشد آبی", callback_data="pic_sm_blue")
        ],
        [
            InlineKeyboardButton(text="🔴 مامور قرمز", callback_data="pic_op_red"),
            InlineKeyboardButton(text="🔵 مامور آبی", callback_data="pic_op_blue")
        ],
        [
            InlineKeyboardButton(text="🚀 شروع بازی", callback_data="pic_start_game")
        ],
        [
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
    buttons.append([InlineKeyboardButton(text="🗺 ارسال مجدد نقشه در پی‌وی", callback_data="pic_resend_key")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_lobby_text(lobby: dict) -> str:
    red_sm = lobby["red_spymaster"]["name"] if lobby["red_spymaster"] else "❌ تعیین نشده"
    blue_sm = lobby["blue_spymaster"]["name"] if lobby["blue_spymaster"] else "❌ تعیین نشده"

    red_ops = ", ".join(lobby["red_operatives"].values()) if lobby["red_operatives"] else "—"
    blue_ops = ", ".join(lobby["blue_operatives"].values()) if lobby["blue_operatives"] else "—"

    return (
        "🖼 **لابی بازی Codenames: Pictures (تصویری)**\n\n"
        "🔴 **تیم قرمز:**\n"
        f"🕵️‍♂️ جاسوس‌ارشد: **{red_sm}**\n"
        f"👥 ماموران: {red_ops}\n\n"
        "🔵 **تیم آبی:**\n"
        f"🕵️‍♂️ جاسوس‌ارشد: **{blue_sm}**\n"
        f"👥 ماموران: {blue_ops}\n\n"
        "▫️ ابعاد تخته: ۵ ستون × ۴ ردیف (۲۰ کارت تصویری)\n"
        "▫️ نقشه کلید بلافاصله پس از شروع بازی به‌صورت **اتوماتیک به پی‌وی هر دو جاسوس‌ارشد** فرستاده می‌شود.\n"
        "⚠️ **توجه:** جاسوس‌های ارشد حتماً باید قبلاً ربات را در پی‌وی Start کرده باشند."
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

    # انتخاب رندوم بنر لابی دقیقاً مانند حالت کلمه‌ای
    banners = [
        os.path.join(os.getcwd(), "assets", "images", f"lobby_banner_{i}.jpg")
        for i in [1, 2, 3]
    ]
    existing_banners = [b for b in banners if os.path.exists(b)]
    banner_file = random.choice(existing_banners) if existing_banners else None

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


@router.callback_query(F.data.in_(["pic_sm_red", "pic_sm_blue", "pic_op_red", "pic_op_blue"]))
async def on_lobby_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lobby = pic_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("لابی منقضی شده است. مجدداً دستور /pictures را بزنید.", show_alert=True)
        return

    user = callback.from_user
    uid = user.id
    uname = user.full_name

    # حذف از رول‌های قبلی جهت جلوگیری از تداخل
    if lobby["red_spymaster"] and lobby["red_spymaster"]["id"] == uid:
        lobby["red_spymaster"] = None
    if lobby["blue_spymaster"] and lobby["blue_spymaster"]["id"] == uid:
        lobby["blue_spymaster"] = None
    lobby["red_operatives"].pop(uid, None)
    lobby["blue_operatives"].pop(uid, None)

    action = callback.data
    if action == "pic_sm_red":
        lobby["red_spymaster"] = {"id": uid, "name": uname}
        await callback.answer("به‌عنوان جاسوس‌ارشد قرمز انتخاب شدید!")
    elif action == "pic_sm_blue":
        lobby["blue_spymaster"] = {"id": uid, "name": uname}
        await callback.answer("به‌عنوان جاسوس‌ارشد آبی انتخاب شدید!")
    elif action == "pic_op_red":
        lobby["red_operatives"][uid] = uname
        await callback.answer("به ماموران قرمز اضافه شدید!")
    elif action == "pic_op_blue":
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
    pic_lobbies.pop(chat_id, None)
    await callback.message.delete()
    await callback.message.answer("❌ لابی بازی تصویری لغو شد.")


@router.callback_query(F.data == "pic_start_game")
async def on_start_game(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    lobby = pic_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("لابی فعالی پیدا نشد.", show_alert=True)
        return

    if not lobby["red_spymaster"] or not lobby["blue_spymaster"]:
        await callback.answer("⚠️ برای شروع مسابقه، هر دو تیم باید یک جاسوس‌ارشد داشته باشند!", show_alert=True)
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
        await callback.answer(f"خطا در ایجاد کارت‌های تصویری: {e}", show_alert=True)
        return

    pic_games[chat_id] = game
    pic_lobbies.pop(chat_id, None)

    # ۱. رندر نقشه رنگی برای جاسوس‌های ارشد
    key_img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio_key = BytesIO()
    key_img.save(bio_key, format="JPEG", quality=92)
    bio_key.seek(0)

    starter_fa = "تیم قرمز 🔴" if game.starter_team == TEAM_RED else "تیم آبی 🔵"
    key_caption = (
        f"🗺 **نقشه محرمانه کلید بازی (Codenames: Pictures)**\n\n"
        f"👑 تیم شروع‌کننده: **{starter_fa}**\n\n"
        f"🔴 اهداف قرمز: {8 if game.starter_team == TEAM_RED else 7} تصویر\n"
        f"🔵 اهداف آبی: {8 if game.starter_team == TEAM_BLUE else 7} تصویر\n"
        f"🟡 شهروندان بی‌طرف: ۴ تصویر\n"
        f"💀 قاتل: ۱ تصویر (مشکی رنگ)\n\n"
        f"⚠️ **خیلی مهم:** این نقشه کاملاً محرمانه است و آن را در گروه ارسال نکنید!"
    )

    # ۲. ارسال خودکار نقشه به پی‌وی هر دو جاسوس‌ارشد
    failed_pms = []
    for sm in (game.red_spymaster, game.blue_spymaster):
        try:
            bio_key.seek(0)
            kf = BufferedInputFile(bio_key.getvalue(), filename="spymaster_key.jpg")
            await callback.bot.send_photo(chat_id=sm["id"], photo=kf, caption=key_caption, parse_mode="Markdown")
        except Exception:
            failed_pms.append(sm["name"])

    # ۳. رندر تخته عمومی بدون رنگ برای گروه
    board_img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio_board = BytesIO()
    board_img.save(bio_board, format="JPEG", quality=92)
    bio_board.seek(0)
    board_file = BufferedInputFile(bio_board.getvalue(), filename="board.jpg")

    extra_warn = ""
    if failed_pms:
        extra_warn = f"⚠️ ربات نتوانست به پی‌وی ({', '.join(failed_pms)}) پیام دهد! لطفاً ابتدا ربات را در پی‌وی Start کنید."

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

    user_id = callback.from_user.id
    # جلوگیری از حدس زدن جاسوس‌های ارشد
    if user_id in (game.red_spymaster["id"], game.blue_spymaster["id"]):
        await callback.answer("جاسوس‌ارشد مجاز به انتخاب کارت نیست!", show_alert=True)
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

    # بازتولید تخته با رنگ کارت فاش‌شده
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

    game.switch_turn()
    await callback.answer("نوبت واگذار شد.")

    board_img = PicturesRenderer.render_board(game, is_spymaster=False)
    bio = BytesIO()
    board_img.save(bio, format="JPEG", quality=92)
    bio.seek(0)

    media = InputMediaPhoto(
        media=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
        caption=_get_game_caption(game, extra="⏭ نوبت توسط تیم واگذار شد."),
        parse_mode="Markdown"
    )
    try:
        await callback.message.edit_media(media=media, reply_markup=build_game_keyboard(game))
    except Exception:
        pass


@router.callback_query(F.data == "pic_resend_key")
async def on_resend_key(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = pic_games.get(chat_id)

    if not game:
        await callback.answer("بازی فعالی پیدا نشد.", show_alert=True)
        return

    user_id = callback.from_user.id
    if user_id not in (game.red_spymaster["id"], game.blue_spymaster["id"]):
        await callback.answer("شما جاسوس‌ارشد این مسابقه نیستید!", show_alert=True)
        return

    key_img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio = BytesIO()
    key_img.save(bio, format="JPEG", quality=92)
    bio.seek(0)
    kf = BufferedInputFile(bio.getvalue(), filename="spymaster_key.jpg")

    try:
        await callback.bot.send_photo(chat_id=user_id, photo=kf, caption="🗺 **نقشه محرمانه Codenames Pictures**\nاین نقشه را در گروه نفرستید!")
        await callback.answer("نقشه در پی‌وی برای شما ارسال شد.", show_alert=True)
    except Exception:
        await callback.answer("ابتدا ربات را در پی‌وی Start کنید تا امکان ارسال پیام وجود داشته باشد.", show_alert=True)


@router.callback_query(F.data == "pic_noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer("این تصویر قبلاً باز شده است.", show_alert=False)
