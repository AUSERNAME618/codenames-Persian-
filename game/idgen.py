import random
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_game_id(length: int = 8) -> str:
    """
    آیدی کوتاه و خوانا برای بازی (مثلاً برای حالت inline: '@bot ABC12XYZ').
    کوتاه نگه داشتنش مهمه چون توی callback_data هم استفاده می‌شه (محدودیت ۶۴ بایتی تلگرام).
    """
    return "".join(random.choices(_ALPHABET, k=length))
