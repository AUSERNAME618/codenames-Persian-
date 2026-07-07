"""
منطق خالص بازی کدنیم.
این ماژول هیچ وابستگی‌ای به aiogram یا تلگرام ندارد و کاملاً قابل تست مستقل است.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Team(str, Enum):
    RED = "red"
    BLUE = "blue"


class Role(str, Enum):
    SPYMASTER = "spymaster"
    OPERATIVE = "operative"


class CardColor(str, Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"


class GameStatus(str, Enum):
    LOBBY = "lobby"          # در حال جمع‌شدن نفرات
    AWAITING_CLUE = "awaiting_clue"  # منتظر تعیین تعداد کلمه توسط اسپای‌مستر
    GUESSING = "guessing"    # مامور‌ها در حال حدس‌زدن
    FINISHED = "finished"    # بازی تمام شده


class GameError(Exception):
    """خطای مربوط به قوانین بازی (مثلاً حرکت غیرمجاز)."""


@dataclass
class Player:
    user_id: int
    name: str
    team: Optional[Team] = None
    role: Optional[Role] = None
    slot: Optional[int] = None  # شماره‌ی اسلات درون گروه تیم+نقش (برای حالت‌های چندمامتوره)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["team"] = self.team.value if self.team else None
        d["role"] = self.role.value if self.role else None
        return d

    @staticmethod
    def from_dict(d: dict) -> "Player":
        return Player(
            user_id=d["user_id"],
            name=d["name"],
            team=Team(d["team"]) if d.get("team") else None,
            role=Role(d["role"]) if d.get("role") else None,
            slot=d.get("slot"),
        )


@dataclass
class Card:
    word: str
    color: CardColor
    revealed: bool = False
    guessed_by: Optional[Team] = None  # کدوم تیم این کارت رو حدس زده (برای ضربدر روی عکس جاسوس)

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "color": self.color.value,
            "revealed": self.revealed,
            "guessed_by": self.guessed_by.value if self.guessed_by else None,
        }

    @staticmethod
    def from_dict(d: dict) -> "Card":
        return Card(
            word=d["word"],
            color=CardColor(d["color"]),
            revealed=d["revealed"],
            guessed_by=Team(d["guessed_by"]) if d.get("guessed_by") else None,
        )


class Game:
    """
    نمایانگر یک بازی/روم کدنیم.
    game_id: شناسه‌ی یکتای بازی (برای حالت inline و دکمه‌ی "انتقال به آخرین پیام")
    chat_id: چت گروهی که بازی در آن در جریان است
    host_id: کاربری که بازی را ساخته (فقط او می‌تواند شروع/تغییر نفرات/خروج بزند)
    """

    def __init__(self, game_id: str, chat_id: int, host_id: int, team_size_mode: int = 4):
        self.game_id = game_id
        self.chat_id = chat_id
        self.host_id = host_id
        self.team_size_mode = team_size_mode  # 4, 6, or 8

        self.status: GameStatus = GameStatus.LOBBY
        self.players: dict[int, Player] = {}  # user_id -> Player

        self.board: list[Card] = []
        self.starting_team: Optional[Team] = None
        self.current_turn: Optional[Team] = None

        # تعداد حدس مجاز در نوبت جاری (بر اساس عددی که اسپای‌مستر تعیین می‌کند)
        self.clue_count: int = 0
        self.clue_word: Optional[str] = None
        self.correct_guesses_this_turn: int = 0

        # برای پیام‌های تلگرام: آیدی آخرین پیام لابی/بازی که فرستاده شده (برای ادیت/حذف)
        self.last_message_id: Optional[int] = None

        self.winner: Optional[Team] = None
        self.ended_by_assassin: bool = False

        self.round_number: int = 1
        # لاگ حدس هر تیم: {"red": [(player_name, word), ...], "blue": [...]}
        self.guess_log: dict[str, list[tuple[str, str]]] = {"red": [], "blue": []}
        # message_id عکس خصوصیِ هر جاسوس در PV خودش (برای ادیت بعد از هر حدس)
        # کلید: user_id (به‌صورت رشته چون کلیدهای JSON همیشه رشته‌ن)، مقدار: message_id
        self.spymaster_message_ids: dict[str, int] = {}

    # ---------- مدیریت نفرات لابی ----------

    def max_operatives_per_team(self) -> int:
        from config import TEAM_SIZE_MODES
        return TEAM_SIZE_MODES[self.team_size_mode]["operatives_per_team"]

    def max_spymasters_per_team(self) -> int:
        from config import TEAM_SIZE_MODES
        return TEAM_SIZE_MODES[self.team_size_mode]["spymasters_per_team"]

    def join_slot(self, user_id: int, name: str, team: Team, role: Role, slot: int) -> None:
        """
        یک بازیکن روی یک اسلات مشخص (مثلاً «مامور تیم آبی - اسلات ۲») کلیک می‌کند.
        اگر خودِ همین کاربر روی همین اسلات دوباره کلیک کنه، از اسلات خارج می‌شه (toggle).
        """
        if self.status != GameStatus.LOBBY:
            raise GameError("بازی از حالت لابی خارج شده است.")

        limit = (
            self.max_spymasters_per_team()
            if role == Role.SPYMASTER
            else self.max_operatives_per_team()
        )
        if slot < 0 or slot >= limit:
            raise GameError("این جایگاه در این حالت وجود ندارد.")

        occupant = next(
            (
                p
                for p in self.players.values()
                if p.team == team and p.role == role and p.slot == slot
            ),
            None,
        )
        if occupant is not None and occupant.user_id == user_id:
            # کلیک روی جایگاه خودش -> خروج از اسلات
            del self.players[user_id]
            return
        if occupant is not None and occupant.user_id != user_id:
            raise GameError("این جایگاه پر است.")

        self.players[user_id] = Player(
            user_id=user_id, name=name, team=team, role=role, slot=slot
        )

    def remove_player(self, user_id: int) -> None:
        self.players.pop(user_id, None)

    def cycle_team_size(self) -> None:
        """دکمه‌ی «تغییر نفرات»: ۴ -> ۶ -> ۸ -> ۴ ..."""
        from config import TEAM_SIZE_CYCLE
        idx = TEAM_SIZE_CYCLE.index(self.team_size_mode)
        self.team_size_mode = TEAM_SIZE_CYCLE[(idx + 1) % len(TEAM_SIZE_CYCLE)]

        # اگر با کوچیک‌شدن ظرفیت، کسی توی اسلاتی مونده که دیگه وجود نداره، حذفش کن
        op_limit = self.max_operatives_per_team()
        sm_limit = self.max_spymasters_per_team()
        to_remove = [
            uid
            for uid, p in self.players.items()
            if (p.role == Role.OPERATIVE and p.slot is not None and p.slot >= op_limit)
            or (p.role == Role.SPYMASTER and p.slot is not None and p.slot >= sm_limit)
        ]
        for uid in to_remove:
            del self.players[uid]

    def is_ready_to_start(self) -> bool:
        """هر دو تیم باید حداقل یک اسپای‌مستر و حداقل یک مامور داشته باشند."""
        for team in (Team.RED, Team.BLUE):
            has_spymaster = any(
                p.team == team and p.role == Role.SPYMASTER for p in self.players.values()
            )
            has_operative = any(
                p.team == team and p.role == Role.OPERATIVE for p in self.players.values()
            )
            if not (has_spymaster and has_operative):
                return False
        return True

    # ---------- شروع بازی ----------

    def start_game(self, word_pool: list[str]) -> None:
        if not self.is_ready_to_start():
            raise GameError("نفرات کافی نیست.")

        from config import (
            BOARD_SIZE, CARDS_PER_STARTING_TEAM, CARDS_PER_OTHER_TEAM,
            CARDS_NEUTRAL, CARDS_ASSASSIN,
        )

        words = random.sample(word_pool, BOARD_SIZE)
        self.starting_team = random.choice([Team.RED, Team.BLUE])
        other_team = Team.BLUE if self.starting_team == Team.RED else Team.RED

        colors = (
            [self.starting_team] * CARDS_PER_STARTING_TEAM
            + [other_team] * CARDS_PER_OTHER_TEAM
            + [CardColor.NEUTRAL] * CARDS_NEUTRAL
            + [CardColor.ASSASSIN] * CARDS_ASSASSIN
        )
        # چون starting_team و other_team از نوع Team هستند نه CardColor، تبدیل می‌کنیم
        colors = [
            CardColor(c.value) if isinstance(c, Team) else c for c in colors
        ]
        random.shuffle(colors)

        self.board = [Card(word=w, color=c) for w, c in zip(words, colors)]
        self.current_turn = self.starting_team
        self.status = GameStatus.AWAITING_CLUE
        self.clue_count = 0
        self.correct_guesses_this_turn = 0
        self.winner = None

    # ---------- روند بازی ----------

    def set_clue_count(self, n: int, word: Optional[str] = None) -> None:
        """اسپای‌مستر تیم فعلی تعداد و کلمه‌ی سرنخ را مشخص می‌کند."""
        if self.status != GameStatus.AWAITING_CLUE:
            raise GameError("الان زمان تعیین تعداد کلمه نیست.")
        if n < 0:
            raise GameError("عدد نامعتبر.")
        self.clue_count = n
        self.clue_word = word
        self.correct_guesses_this_turn = 0
        self.status = GameStatus.GUESSING

    def can_end_guessing(self) -> bool:
        """دکمه‌ی «اتمام حدس» فقط وقتی فعال است که به سقفِ حدسِ درستِ تعیین‌شده رسیده باشند."""
        return self.correct_guesses_this_turn >= self.clue_count

    def guess(self, cell_index: int, player_name: str) -> CardColor:
        """
        یک مامور روی یک خانه کلیک می‌کند.
        خروجی رنگ کارتی است که فاش شد، تا لایه‌ی بالاتر (هندلر تلگرام) پیام مناسب بدهد.
        """
        if self.status != GameStatus.GUESSING:
            raise GameError("الان نوبت حدس‌زدن نیست.")
        card = self.board[cell_index]
        if card.revealed:
            raise GameError("این خانه قبلاً فاش شده است.")

        card.revealed = True
        card.guessed_by = self.current_turn
        self.guess_log[self.current_turn.value].append((player_name, card.word))
        current_team_color = CardColor(self.current_turn.value)

        if card.color == CardColor.ASSASSIN:
            self.winner = Team.BLUE if self.current_turn == Team.RED else Team.RED
            self.status = GameStatus.FINISHED
            self.ended_by_assassin = True
            self._reveal_all()
            return card.color

        if card.color == current_team_color:
            self.correct_guesses_this_turn += 1
            if self._check_team_win(self.current_turn):
                self.winner = self.current_turn
                self.status = GameStatus.FINISHED
                self._reveal_all()
            return card.color

        # رنگ اشتباه (تیم مقابل یا خنثی) -> نوبت خودکار عوض می‌شود
        if self._check_team_win_after_wrong_guess():
            self.status = GameStatus.FINISHED
            self._reveal_all()
        else:
            self._switch_turn()
        return card.color

    def end_turn(self) -> None:
        """دکمه‌ی «پایان دست»: مامورها به‌طور کامل از حدس‌زدن در این دست صرف‌نظر می‌کنند."""
        if self.status != GameStatus.GUESSING:
            raise GameError("الان دستی برای پایان‌دادن نیست.")
        self._switch_turn()

    def end_guessing(self) -> None:
        """دکمه‌ی «اتمام حدس»: فقط اگر به سقف حدس درست رسیده باشند مجاز است."""
        if self.status != GameStatus.GUESSING:
            raise GameError("الان دستی برای پایان‌دادن نیست.")
        if not self.can_end_guessing():
            raise GameError("هنوز به تعداد سرنخ تعیین‌شده حدس نزده‌اید.")
        self._switch_turn()

    def _switch_turn(self) -> None:
        self.current_turn = Team.BLUE if self.current_turn == Team.RED else Team.RED
        self.clue_count = 0
        self.clue_word = None
        self.correct_guesses_this_turn = 0
        self.status = GameStatus.AWAITING_CLUE
        self.round_number += 1

    def _reveal_all(self) -> None:
        """وقتی بازی تمام می‌شود، کل نقشه برای همه فاش می‌شود."""
        for c in self.board:
            c.revealed = True

    def _check_team_win(self, team: Team) -> bool:
        """اگر همه‌ی کارت‌های این تیم فاش شده باشند، همین تیم برنده است."""
        team_color = CardColor(team.value)
        remaining = [c for c in self.board if c.color == team_color and not c.revealed]
        return len(remaining) == 0

    def _check_team_win_after_wrong_guess(self) -> bool:
        """بعد از حدس اشتباه، بررسی کن که آیا با فاش‌شدن یک کارتِ تیمِ مقابل، آن تیم همین الان برنده شده."""
        for team in (Team.RED, Team.BLUE):
            if self._check_team_win(team):
                self.winner = team
                return True
        return False

    # ---------- سریالایز برای ذخیره در SQLite ----------

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "chat_id": self.chat_id,
            "host_id": self.host_id,
            "team_size_mode": self.team_size_mode,
            "status": self.status.value,
            "players": [p.to_dict() for p in self.players.values()],
            "board": [c.to_dict() for c in self.board],
            "starting_team": self.starting_team.value if self.starting_team else None,
            "current_turn": self.current_turn.value if self.current_turn else None,
            "clue_count": self.clue_count,
            "clue_word": self.clue_word,
            "correct_guesses_this_turn": self.correct_guesses_this_turn,
            "last_message_id": self.last_message_id,
            "winner": self.winner.value if self.winner else None,
            "ended_by_assassin": self.ended_by_assassin,
            "round_number": self.round_number,
            "guess_log": self.guess_log,
            "spymaster_message_ids": self.spymaster_message_ids,
        }

    @staticmethod
    def from_dict(d: dict) -> "Game":
        g = Game(
            game_id=d["game_id"],
            chat_id=d["chat_id"],
            host_id=d["host_id"],
            team_size_mode=d["team_size_mode"],
        )
        g.status = GameStatus(d["status"])
        g.players = {p["user_id"]: Player.from_dict(p) for p in d["players"]}
        g.board = [Card.from_dict(c) for c in d["board"]]
        g.starting_team = Team(d["starting_team"]) if d["starting_team"] else None
        g.current_turn = Team(d["current_turn"]) if d["current_turn"] else None
        g.clue_count = d["clue_count"]
        g.clue_word = d.get("clue_word")
        g.correct_guesses_this_turn = d["correct_guesses_this_turn"]
        g.last_message_id = d["last_message_id"]
        g.winner = Team(d["winner"]) if d["winner"] else None
        g.ended_by_assassin = d.get("ended_by_assassin", False)
        g.round_number = d.get("round_number", 1)
        raw_log = d.get("guess_log", {"red": [], "blue": []})
        g.guess_log = {
            "red": [tuple(x) for x in raw_log.get("red", [])],
            "blue": [tuple(x) for x in raw_log.get("blue", [])],
        }
        g.spymaster_message_ids = d.get("spymaster_message_ids", {})
        return g

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def from_json(s: str) -> "Game":
        return Game.from_dict(json.loads(s))
