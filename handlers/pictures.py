"""
handlers/pictures.py
ماژول کامل و فوق‌حرفه‌ای Codenames: Pictures
- رندر کامل با پنل‌های دوطرفه، لاگ حدس‌ها، کادر سرنخ، بنر وضعیت و فونت پفک
- کارت‌های درشت تصویری (اشغال بیش از ۶۰٪ صفحه) با اورلی کامل
- آپدیت خودکار و بی‌صدای نقشه در پی‌وی جاسوس‌ها با protect_content
- لابی استاندارد با ظرفیت قانونی (حداقل ۴ نفر)
"""

import os
import glob
import random
import logging
from io import BytesIO
from typing import List, Dict, Optional, Tuple

import arabic_reshaper
from bidi.algorithm import get_display
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


def fa(text: str) -> str:
    """تنظیم و اتصال حروف فارسی برای Pillow"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)


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

        # اطلاعات سرنخ و لاگ‌ها
        self.current_clue: Optional[str] = None
        self.current_count: Optional[int] = None
        self.winner: Optional[str] = None
        self.logs: Dict[str, List[str]] = {TEAM_RED: [], TEAM_BLUE: []}

        # شناسه پیام نقشه در پی‌وی جاسوس‌ها برای ادیت بی‌صدا
        self.spymaster_msg_ids: Dict[int, int] = {}
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

        # تقسیم دقیق نقش‌های Codenames: Pictures: 8 + 7 + 4 + 1 = 20
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

    @property
    def red_remaining(self) -> int:
        return self.starter_remaining if self.starter_team == TEAM_RED else self.second_remaining

    @property
    def blue_remaining(self) -> int:
        return self.starter_remaining if self.starter_team == TEAM_BLUE else self.second_remaining

    def reveal_card(self, index: int, player_name: str) -> Tuple[bool, PictureCard, Optional[str]]:
        card = self.cards[index - 1]
        if card.revealed:
            return True, card, None

        card.revealed = True
        guessing_team = self.current_turn

        # ثبت لاگ برای تیم حدس‌زننده
        log_entry = f"(تصویر {card.index} : {player_name})"
        self.logs[guessing_team].append(log_entry)

        # ۱. حدس قاتل
        if card.role == ROLE_ASSASSIN:
            self.winner = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED
            return False, card, self.winner

        # ۲. حدس کارت خودی
        if card.team == self.current_turn:
            if self.current_turn == self.starter_team:
                self.starter_remaining -= 1
            else:
                self.second_remaining -= 1

            if self.starter_remaining == 0:
                self.winner = self.starter_team
                return False, card, self.winner
            if self.second_remaining == 0:
                self.winner = self.second_team
                return False, card, self.winner

            return True, card, None

        # ۳. حدس کارت حریف
        elif card.team is not None and card.team != self.current_turn:
            if card.team == self.starter_team:
                self.starter_remaining -= 1
            else:
                self.second_remaining -= 1

            self.switch_turn()

            if self.starter_remaining == 0:
                self.winner = self.starter_team
                return False, card, self.winner
            if self.second_remaining == 0:
                self.winner = self.second_team
                return False, card, self.winner

            return True, card, None
        else:
            # ۴. شهروند بی‌طرف (کرمی خاکی)
            self.switch_turn()
            return True, card, None

    def switch_turn(self):
        self.current_turn = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED
        self.current_clue = None
        self.current_count = None


# ==========================================
# سیستم رندر اختصاصی مشابه نسخه کلماتی
# ==========================================

class PicturesRenderer:
    @staticmethod
    def render_board(game: PicturesGameSession, is_spymaster: bool = False) -> Image.Image:
        # ابعاد دقیق و گسترده بوم تصویر
        CANVAS_W = 1440
        CANVAS_H = 920

        board = Image.new("RGBA", (CANVAS_W, CANVAS_H), (11, 47, 82, 255))
        draw = ImageDraw.Draw(board)

        # رسم شبکه نقطه‌ای بک‌گراند مشابه رندر کلماتی
        dot_color = (25, 75, 120, 180)
        for dx in range(12, CANVAS_W, 24):
            for dy in range(12, CANVAS_H, 24):
                draw.ellipse([dx - 1.5, dy - 1.5, dx + 1.5, dy + 1.5], fill=dot_color)

        # انتخاب فونت‌های اصلی پروژه
        font_dir = os.path.join(os.getcwd(), "assets", "fonts")
        def load_font(name: str, size: int):
            path = os.path.join(font_dir, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
            for sys_font in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
                try:
                    return ImageFont.truetype(sys_font, size)
                except Exception:
                    pass
            return ImageFont.load_default()

        font_header = load_font("Pofak-ExtraBold.ttf", 36)
        font_sub = load_font("Pofak-Medium.ttf", 20)
        font_panel_title = load_font("Pofak-ExtraBold.ttf", 24)
        font_panel_section = load_font("Pofak-DemiBold.ttf", 18)
        font_panel_text = load_font("Pofak-Medium.ttf", 16)
        font_badge = load_font("Pofak-ExtraBold.ttf", 20)
        font_card_num = load_font("Pofak-ExtraBold.ttf", 24)
        font_clue = load_font("Pofak-ExtraBold.ttf", 26)
        font_log = load_font("Pofak-Medium.ttf", 14)

        # ----------------------------------------------------
        # ۱. بنر وضعیت در بالای تصویر
        # ----------------------------------------------------
        if game.winner:
            winner_text = "تیم قرمز برنده شد" if game.winner == TEAM_RED else "تیم آبی برنده شد"
            h_text = fa(winner_text)
        else:
            turn_text = "نوبت تیم قرمز" if game.current_turn == TEAM_RED else "نوبت تیم آبی"
            h_text = fa(turn_text)

        bbox_h = font_header.getbbox(h_text)
        draw.text(((CANVAS_W - (bbox_h[2] - bbox_h[0])) / 2, 22), h_text, fill=(255, 255, 255), font=font_header)

        # اسامی بازیکنان نوبت جاری در زیر عنوان
        if game.current_turn == TEAM_RED:
            sub_names = f"{game.red_spymaster['name']} • " + " ، ".join(list(game.red_operatives.values())[:3])
        else:
            sub_names = f"{game.blue_spymaster['name']} • " + " ، ".join(list(game.blue_operatives.values())[:3])
        sub_text = fa(sub_names)
        bbox_sub = font_sub.getbbox(sub_text)
        draw.text(((CANVAS_W - (bbox_sub[2] - bbox_sub[0])) / 2, 72), sub_text, fill=(185, 215, 245), font=font_sub)

        # ----------------------------------------------------
        # ۲. پنل‌های کناری (چپ: تیم آبی | راست: تیم قرمز)
        # ----------------------------------------------------
        PANEL_W = 210
        PANEL_H = 490
        PANEL_Y = 120

        # --- پنل تیم آبی (سمت چپ) ---
        blue_box = [30, PANEL_Y, 30 + PANEL_W, PANEL_Y + PANEL_H]
        draw.rounded_rectangle(blue_box, radius=18, fill=(29, 133, 208, 255))

        # عنوان تیم آبی و دایره تعداد باقی‌مانده
        draw.text((45, PANEL_Y + 16), fa("تیم آبی"), fill=(255, 255, 255), font=font_panel_title)
        draw.ellipse([200, PANEL_Y + 14, 230, PANEL_Y + 44], fill=(255, 255, 255, 255))
        rem_blue_str = str(game.blue_remaining)
        rb_box = font_badge.getbbox(rem_blue_str)
        draw.text((215 - (rb_box[0] + rb_box[2]) / 2, PANEL_Y + 29 - (rb_box[1] + rb_box[3]) / 2), rem_blue_str, fill=(29, 133, 208), font=font_badge)

        # بخش ماموران حدس آبی
        draw.text((45, PANEL_Y + 70), fa("مامورین حدس"), fill=(12, 50, 85), font=font_panel_section)
        op_y = PANEL_Y + 98
        for op in list(game.blue_operatives.values())[:4]:
            draw.text((45, op_y), fa(op), fill=(255, 255, 255), font=font_panel_text)
            op_y += 24

        # بخش جاسوس آبی
        draw.text((45, PANEL_Y + 220), fa("جاسوس"), fill=(12, 50, 85), font=font_panel_section)
        draw.text((45, PANEL_Y + 248), fa(game.blue_spymaster["name"]), fill=(255, 255, 255), font=font_panel_title)

        # --- پنل تیم قرمز (سمت راست) ---
        red_box = [CANVAS_W - 30 - PANEL_W, PANEL_Y, CANVAS_W - 30, PANEL_Y + PANEL_H]
        draw.rounded_rectangle(red_box, radius=18, fill=(214, 48, 49, 255))

        # عنوان تیم قرمز و دایره تعداد باقی‌مانده
        draw.text((CANVAS_W - 30 - PANEL_W + 15, PANEL_Y + 16), fa("تیم قرمز"), fill=(255, 255, 255), font=font_panel_title)
        draw.ellipse([CANVAS_W - 60, PANEL_Y + 14, CANVAS_W - 30, PANEL_Y + 44], fill=(255, 255, 255, 255))
        rem_red_str = str(game.red_remaining)
        rr_box = font_badge.getbbox(rem_red_str)
        draw.text((CANVAS_W - 45 - (rr_box[0] + rr_box[2]) / 2, PANEL_Y + 29 - (rr_box[1] + rr_box[3]) / 2), rem_red_str, fill=(214, 48, 49), font=font_badge)

        # بخش ماموران حدس قرمز
        draw.text((CANVAS_W - 30 - PANEL_W + 15, PANEL_Y + 70), fa("مامورین حدس"), fill=(85, 12, 12), font=font_panel_section)
        op_y = PANEL_Y + 98
        for op in list(game.red_operatives.values())[:4]:
            draw.text((CANVAS_W - 30 - PANEL_W + 15, op_y), fa(op), fill=(255, 255, 255), font=font_panel_text)
            op_y += 24

        # بخش جاسوس قرمز
        draw.text((CANVAS_W - 30 - PANEL_W + 15, PANEL_Y + 220), fa("جاسوس"), fill=(85, 12, 12), font=font_panel_section)
        draw.text((CANVAS_W - 30 - PANEL_W + 15, PANEL_Y + 248), fa(game.red_spymaster["name"]), fill=(255, 255, 255), font=font_panel_title)

        # ----------------------------------------------------
        # ۳. لاگ حدس‌های هر تیم در زیر پنل‌ها
        # ----------------------------------------------------
        # لاگ تیم آبی
        log_y = PANEL_Y + PANEL_H + 18
        for entry in game.logs[TEAM_BLUE][-7:]:
            draw.text((32, log_y), fa(entry), fill=(240, 245, 255), font=font_log)
            log_y += 22

        # لاگ تیم قرمز
        log_y = PANEL_Y + PANEL_H + 18
        for entry in game.logs[TEAM_RED][-7:]:
            draw.text((CANVAS_W - 30 - PANEL_W + 12, log_y), fa(entry), fill=(240, 245, 255), font=font_log)
            log_y += 22

        # ----------------------------------------------------
        # ۴. شبکه کارت‌های تصویری (اختصاص ۶۳٪ عرض و ۷۱٪ ارتفاع)
        # ----------------------------------------------------
        CARD_W = 168
        CARD_H = 148
        GAP_X = 18
        GAP_Y = 16
        GRID_W = (COLS * CARD_W) + ((COLS - 1) * GAP_X)
        GRID_START_X = int((CANVAS_W - GRID_W) / 2)
        GRID_START_Y = PANEL_Y

        # ماسک گوشه‌های گرد برای هر کارت
        mask = Image.new("L", (CARD_W, CARD_H), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, CARD_W, CARD_H], radius=14, fill=255)

        for idx, card in enumerate(game.cards):
            r = idx // COLS
            c = idx % COLS
            x = GRID_START_X + c * (CARD_W + GAP_X)
            y = GRID_START_Y + r * (CARD_H + GAP_Y)

            try:
                with Image.open(card.image_path) as img:
                    card_img = img.convert("RGBA").resize((CARD_W, CARD_H), Image.Resampling.LANCZOS)
            except Exception:
                card_img = Image.new("RGBA", (CARD_W, CARD_H), (50, 55, 65, 255))

            card_img.putalpha(mask)

            overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            card_color = COLOR_MAP[card.team] if card.team else COLOR_MAP[card.role]

            if card.revealed:
                # اورلی کامل، شفاف و یکدست روی کل تصویر فاش‌شده
                overlay_draw.rectangle([0, 0, CARD_W, CARD_H], fill=(*card_color, 180))
                overlay_draw.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, outline=(*card_color, 255), width=5)
            elif is_spymaster:
                # دید محرمانه جاسوس‌ارشد: اورلی ملایم با حاشیه رنگی ضخیم
                overlay_draw.rectangle([0, 0, CARD_W, CARD_H], fill=(*card_color, 110))
                overlay_draw.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, outline=(*card_color, 255), width=6)
            else:
                overlay_draw.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, outline=(110, 140, 175, 200), width=2)

            # دایره پلاک شماره کارت (بالا سمت چپ با تراز دقیق مرکز)
            badge_r = 16
            badge_cx = 24
            badge_cy = 24

            badge_fill = (14, 18, 24, 235)
            badge_outline = (255, 255, 255, 240)
            overlay_draw.ellipse(
                [badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r],
                fill=badge_fill,
                outline=badge_outline,
                width=2
            )

            num_str = str(card.index)
            bbox = font_card_num.getbbox(num_str)
            tx = badge_cx - (bbox[0] + bbox[2]) / 2
            ty = badge_cy - (bbox[1] + bbox[3]) / 2
            overlay_draw.text((tx, ty), num_str, fill=(255, 255, 255), font=font_card_num)

            card_composite = Image.alpha_composite(card_img, overlay)
            board.paste(card_composite, (x, y), mask)

        # ----------------------------------------------------
        # ۵. باکس سرنخ و تعداد حدس در پایین مرکز تخته
        # ----------------------------------------------------
        CLUE_BOX_W = 320
        CLUE_BOX_H = 54
        CLUE_COUNT_W = 54
        TOTAL_CLUE_W = CLUE_BOX_W + 12 + CLUE_COUNT_W
        CLUE_START_X = int((CANVAS_W - TOTAL_CLUE_W) / 2)
        CLUE_Y = 788

        # باکس کپسولی سفید سرنخ
        clue_rect = [CLUE_START_X, CLUE_Y, CLUE_START_X + CLUE_BOX_W, CLUE_Y + CLUE_BOX_H]
        draw.rounded_rectangle(clue_rect, radius=27, fill=(255, 255, 255, 255))

        clue_display = game.current_clue if game.current_clue else "در انتظار سرنخ..."
        clue_fa = fa(clue_display)
        c_box = font_clue.getbbox(clue_fa)
        draw.text(
            (CLUE_START_X + (CLUE_BOX_W - (c_box[2] - c_box[0])) / 2, CLUE_Y + 12),
            clue_fa,
            fill=(30, 39, 46),
            font=font_clue
        )

        # باکس مربعی سفید تعداد حدس
        count_rect = [CLUE_START_X + CLUE_BOX_W + 12, CLUE_Y, CLUE_START_X + TOTAL_CLUE_W, CLUE_Y + CLUE_BOX_H]
        draw.rounded_rectangle(count_rect, radius=14, fill=(255, 255, 255, 255))

        count_display = str(game.current_count) if game.current_count is not None else "—"
        cnt_box = font_clue.getbbox(count_display)
        draw.text(
            (count_rect[0] + (CLUE_COUNT_W - (cnt_box[2] - cnt_box[0])) / 2, CLUE_Y + 12),
            count_display,
            fill=(30, 39, 46),
            font=font_clue
        )

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
        "🎮 **لابی مسابقه کدنیمز تصویری (Codenames: Pictures)**\n\n"
        "🔴 **تیم قرمز:**\n"
        f"🕵️‍♂️ جاسوس‌ارشد: **{red_sm}**\n"
        f"👥 ماموران: {red_ops}\n\n"
        "🔵 **تیم آبی:**\n"
        f"🕵️‍♂️ جاسوس‌ارشد: **{blue_sm}**\n"
        f"👥 ماموران: {blue_ops}\n\n"
        "▫️ ابعاد تخته: ۵ ستون × ۴ ردیف (۲۰ تصویر)\n"
        "▫️️ شروع مسابقه نیازمند حداقل ۴ بازیکن (یک جاسوس‌ارشد و حداقل یک مامور برای هر تیم) است.\n"
        "⚠️ **توجه:** جاسوس‌های ارشد حتماً باید قبل از شروع، ربات را در پی‌وی Start کرده باشند."
    )


def _get_game_caption(game: PicturesGameSession, extra: str = "") -> str:
    turn_fa = "تیم قرمز 🔴" if game.current_turn == TEAM_RED else "تیم آبی 🔵"
    red_sm = game.red_spymaster["name"]
    blue_sm = game.blue_spymaster["name"]

    text = (
        f"🖼 **مسابقه Codenames: Pictures**\n"
        f"👑 نوبت: **{turn_fa}**\n\n"
        f"🔴 اهداف قرمز: **{game.red_remaining}** (جاسوس‌ارشد: {red_sm})\n"
        f"🔵 اهداف آبی: **{game.blue_remaining}** (جاسوس‌ارشد: {blue_sm})\n\n"
        f"نوبت جاسوس‌ارشد {turn_fa} است که سرنخ بفرستد (مثال: `دریا ۲`).\n"
        f"ماموران برای حدس تصویر روی شماره آن کلیک کنند:"
    )
    if extra:
        text = f"{extra}\n\n" + text
    return text


async def _update_spymaster_maps(bot: Bot, game: PicturesGameSession):
    """آپدیت بی‌صدا و زنده نقشه در پی‌وی هر دو جاسوس‌ارشد بدون ارسال متن"""
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

    # بررسی سخت‌گیرانه شرط حداقل ۴ نفر
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

    # رندر نقشه برای جاسوس‌های ارشد
    key_img = PicturesRenderer.render_board(game, is_spymaster=True)
    bio_key = BytesIO()
    key_img.save(bio_key, format="JPEG", quality=92)
    bio_key.seek(0)
    bytes_key = bio_key.getvalue()

    # ارسال نقشه به پی‌وی بدون متن و با قابلیت ضد فوروارد (protect_content)
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


# ثبت سرنخ متنی ارسالی توسط جاسوس‌ارشد در گروه
@router.message(F.text & ~F.text.startswith("/"))
async def on_spymaster_clue_msg(message: Message):
    chat_id = message.chat.id
    game = pic_games.get(chat_id)
    if not game or game.winner:
        return

    uid = message.from_user.id
    current_sm = game.red_spymaster if game.current_turn == TEAM_RED else game.blue_spymaster
    if uid != current_sm["id"]:
        return

    parts = message.text.strip().split()
    if len(parts) >= 2 and parts[-1].isdigit():
        clue_word = " ".join(parts[:-1])
        clue_count = int(parts[-1])

        game.current_clue = clue_word
        game.current_count = clue_count

        # به‌روزرسانی زنده نقشه پی‌وی و تخته گروه
        await _update_spymaster_maps(message.bot, game)

        board_img = PicturesRenderer.render_board(game, is_spymaster=False)
        bio = BytesIO()
        board_img.save(bio, format="JPEG", quality=92)
        bio.seek(0)

        turn_fa = "قرمز 🔴" if game.current_turn == TEAM_RED else "آبی 🔵"
        await message.reply_photo(
            photo=BufferedInputFile(bio.getvalue(), filename="board.jpg"),
            caption=f"🗣 **سرنخ جاسوس‌ارشد {turn_fa}:** `{clue_word}` برای **{clue_count}** تصویر\nماموران تیم اکنون می‌توانید حدس بزنید:",
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
    if uid in (game.red_spymaster["id"], game.blue_spymaster["id"]):
        await callback.answer("جاسوس‌ارشد اجازه حدس زدن ندارد!", show_alert=True)
        return

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
    is_continue, card, winner = game.reveal_card(card_idx, callback.from_user.full_name)

    extra_msg = ""
    if winner:
        winner_fa = "تیم قرمز 🔴" if winner == TEAM_RED else "تیم آبی 🔵"
        extra_msg = f"🏆 **پایان بازی! {winner_fa} برنده مسابقه شد!**"
        pic_games.pop(chat_id, None)

    # آپدیت بی‌صدا و زنده در پی‌وی هر دو جاسوس‌ارشد
    await _update_spymaster_maps(callback.bot, game)

    # بازتولید تخته مسابقه در گروه
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
        await callback.answer("تنها ماموران نوبت جاری اجازه پایان نوبت را دارند.", show_alert=True)
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
