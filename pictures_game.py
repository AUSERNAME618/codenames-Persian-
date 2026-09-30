"""
pictures_game.py
ماژول اختصاصی Codenames Pictures
- شبکه 5x4 (۲۰ تصویر)
- نقش‌ها: ۸ تیم اول، ۷ تیم دوم، ۴ شهروند، ۱ قاتل
- رندر هوشمند با پلاک عددی خوانا روی هر کارت
"""

import os
import glob
import random
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
    TEAM_RED: (220, 53, 69),        # قرمز
    TEAM_BLUE: (30, 144, 255),      # آبی
    ROLE_BYSTANDER: (218, 165, 32), # زرد/کرم خنثی
    ROLE_ASSASSIN: (25, 25, 25),    # مشکی
}


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
        all_images = glob.glob(os.path.join(self.pictures_dir, "*.webp"))
        if len(all_images) < TOTAL_PICTURES:
            raise ValueError(f"حداقل {TOTAL_PICTURES} تصویر در مسیر {self.pictures_dir} پیدا نشد!")

        selected_images = random.sample(all_images, TOTAL_PICTURES)

        # تقسیم دقیق نقش‌های استاندارد Pictures: 8 + 7 + 4 + 1 = 20
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
        
        # ۱. حدس قاتل
        if card.role == ROLE_ASSASSIN:
            winner = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED
            return False, card, winner

        # ۲. حدس ایجنت تیم جاری
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

        # ۳. حدس اشتباه: کارت متعلق به تیم حریف
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

        # ۴. حدس اشتباه: شهروند خنثی
        else:
            self.switch_turn()
            return True, card, None

    def switch_turn(self):
        self.current_turn = TEAM_BLUE if self.current_turn == TEAM_RED else TEAM_RED


class PicturesRenderer:
    @staticmethod
    def render_board(game: PicturesGameSession, is_spymaster: bool = False, thumb_size: int = 220) -> Image.Image:
        card_w, card_h = thumb_size, thumb_size
        padding = 12
        margin = 18

        board_w = (COLS * card_w) + ((COLS - 1) * padding) + (2 * margin)
        board_h = (ROWS * card_h) + ((ROWS - 1) * padding) + (2 * margin)

        board = Image.new("RGBA", (board_w, board_h), (26, 27, 30, 255))
        draw = ImageDraw.Draw(board)

        # تلاش برای انتخاب فونت مناسب برای شماره‌ها
        font = None
        for font_name in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "tahoma.ttf"]:
            try:
                font = ImageFont.truetype(font_name, 22)
                break
            except IOError:
                continue
        if font is None:
            font = ImageFont.load_default()

        for idx, card in enumerate(game.cards):
            r = idx // COLS
            c = idx % COLS
            x = margin + c * (card_w + padding)
            y = margin + r * (card_h + padding)

            # لود عکس
            try:
                with Image.open(card.image_path) as img:
                    card_img = img.convert("RGBA").resize((card_w, card_h), Image.Resampling.LANCZOS)
            except Exception:
                card_img = Image.new("RGBA", (card_w, card_h), (70, 70, 70, 255))

            overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            card_color = COLOR_MAP[card.team] if card.team else COLOR_MAP[card.role]

            if card.revealed:
                # لایه شفاف روی کارت فاش‌شده
                overlay_draw.rectangle([0, 0, card_w, card_h], fill=(*card_color, 160))
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=card_color, width=4)
            elif is_spymaster:
                # دید اسپای‌مستر
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=card_color, width=6)
                overlay_draw.ellipse([card_w - 36, 10, card_w - 10, 36], fill=(*card_color, 240))
                overlay_draw.ellipse([card_w - 36, 10, card_w - 10, 36], outline=(255, 255, 255), width=2)
            else:
                overlay_draw.rectangle([0, 0, card_w - 1, card_h - 1], outline=(120, 120, 120, 180), width=2)

            # پلاک شماره کارت (بالا چپ - با کادر تیره و عدد کاملاً درشت)
            badge_w, badge_h = 42, 34
            badge_box = [8, 8, 8 + badge_w, 8 + badge_h]
            overlay_draw.rounded_rectangle(badge_box, radius=8, fill=(15, 15, 15, 220), outline=(255, 255, 255, 180), width=1)
            
            num_str = str(card.index)
            overlay_draw.text((16 if len(num_str) == 1 else 10, 12), num_str, fill=(255, 255, 255), font=font)

            card_composite = Image.alpha_composite(card_img, overlay)
            board.paste(card_composite, (x, y))

        return board.convert("RGB")


def build_pictures_keyboard(game: PicturesGameSession) -> InlineKeyboardMarkup:
    """
    ساخت دکمه‌های متناظر با شبکه ۵×۴ و نمایش همزمان شماره و وضعیت
    """
    keyboard = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            idx = r * COLS + c
            card = game.cards[idx]
            
            if card.revealed:
                if card.role == ROLE_ASSASSIN:
                    btn_text = f"💀 {card.index}"
                elif card.role == ROLE_BYSTANDER:
                    btn_text = f"⬜️ {card.index}"
                elif card.team == TEAM_RED:
                    btn_text = f"🟥 {card.index}"
                else:
                    btn_text = f"🟦 {card.index}"
            else:
                btn_text = f" {card.index} "

            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"pic_guess_{card.index}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("پایان نوبت / رد کردن ⏭", callback_data="pic_pass")])
    return InlineKeyboardMarkup(keyboard)
